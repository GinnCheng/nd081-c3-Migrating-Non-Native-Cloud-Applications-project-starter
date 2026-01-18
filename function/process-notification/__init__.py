import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import azure.functions as func
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def _get_env(name: str, default: Optional[str] = None) -> str:
    v = os.environ.get(name, default)
    if v is None or str(v).strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def _db_connect():
    host = _get_env("POSTGRES_URL")
    dbname = _get_env("POSTGRES_DB")
    user = _get_env("POSTGRES_USER")
    password = _get_env("POSTGRES_PW")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))

    return psycopg2.connect(
        host=host,
        dbname=dbname,
        user=user,
        password=password,
        port=port,
        sslmode="require",  # Azure PostgreSQL 通常需要 SSL
    )


def _parse_notification_id(body_text: str) -> int:
    t = body_text.strip()

    # 允许两种格式：
    # 1) "123"
    # 2) JSON: {"notification_id": 123}
    try:
        return int(t)
    except ValueError:
        pass

    try:
        obj = json.loads(t)
        nid = obj.get("notification_id")
        return int(nid)
    except Exception as e:
        raise ValueError(f"Cannot parse notification id from message: {t}") from e


def _send_email(to_email: str, subject: str, body: str) -> None:
    api_key = os.environ.get("SENDGRID_API_KEY", "")
    from_email = os.environ.get("ADMIN_EMAIL_ADDRESS", "info@techconf.com")

    # 没有 key：直接跳过，不要报错
    if not api_key:
        logging.info("SENDGRID_API_KEY not set. Skipping email to %s", to_email)
        return

    try:
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
        )
        SendGridAPIClient(api_key).send(message)
    except Exception as e:
        # 关键：吞掉异常，让函数继续跑完并更新 DB 状态
        logging.exception("SendGrid send failed. Skipping email to %s. Error: %s", to_email, e)
        return


def _fetch_one(cur, query: str, params: Tuple[Any, ...]) -> Optional[Dict[str, Any]]:
    cur.execute(query, params)
    return cur.fetchone()


def _fetch_all(cur, query: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
    cur.execute(query, params)
    return cur.fetchall()


def _try_queries_for_tables(conn, notification_id: int):
    """
    兼容表名是单数/复数的两种情况：
      notification + attendee
      notifications + attendees
    """
    candidates = [
        ("notification", "attendee"),
        ("notifications", "attendees"),
    ]

    last_err = None
    for notif_table, attendee_table in candidates:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                notif_q = f"""
                    SELECT id, subject, message
                    FROM {notif_table}
                    WHERE id = %s
                """
                notif = _fetch_one(cur, notif_q, (notification_id,))
                if not notif:
                    raise RuntimeError(f"Notification id={notification_id} not found in table '{notif_table}'")

                att_q = f"""
                    SELECT first_name, email
                    FROM {attendee_table}
                """
                attendees = _fetch_all(cur, att_q)

                return notif_table, attendee_table, notif, attendees
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Failed querying notification/attendee tables with known candidates: {last_err}") from last_err


def _update_notification(conn, notif_table: str, notification_id: int, status: str) -> None:
    completed = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        q = f"""
            UPDATE {notif_table}
            SET status = %s, completed_date = %s
            WHERE id = %s
        """
        cur.execute(q, (status, completed, notification_id))


def main(msg: func.ServiceBusMessage) -> None:
    raw = msg.get_body().decode("utf-8")
    logging.info("Received Service Bus message: %s", raw)

    notification_id = _parse_notification_id(raw)
    logging.info("Parsed notification_id=%s", notification_id)

    conn = None
    try:
        conn = _db_connect()
        conn.autocommit = False

        notif_table, attendee_table, notif, attendees = _try_queries_for_tables(conn, notification_id)

        subject_template = (notif.get("subject") or "").strip()
        body = (notif.get("message") or "").strip()

        count = 0
        for a in attendees:
            email = (a.get("email") or "").strip()
            first_name = (a.get("first_name") or "").strip()

            if not email:
                continue

            personalized_subject = f"{first_name}: {subject_template}" if first_name else subject_template
            _send_email(email, personalized_subject, body)
            count += 1

        _update_notification(conn, notif_table, notification_id, f"Notified {count} attendees")
        conn.commit()

        logging.info(
            "Done. notification_id=%s, attendees_notified=%s, tables=%s/%s",
            notification_id, count, notif_table, attendee_table
        )

    except Exception as e:
        if conn:
            conn.rollback()
        logging.exception("Function failed for notification_id=%s: %s", notification_id, e)
        raise
    finally:
        if conn:
            conn.close()
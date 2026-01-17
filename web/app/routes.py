from app import app, db
from datetime import datetime
from app.models import Attendee, Conference, Notification
from flask import render_template, session, request, redirect, url_for, flash, make_response
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import logging


def enqueue_notification(notification_id: int) -> None:
    conn_str = app.config.get("SERVICE_BUS_CONNECTION_STRING")
    queue_name = app.config.get("SERVICE_BUS_QUEUE_NAME")

    if not conn_str or not queue_name:
        raise RuntimeError("Service Bus config missing: SERVICE_BUS_CONNECTION_STRING / SERVICE_BUS_QUEUE_NAME")

    # # 发送 notification_id（通常用字符串/JSON；这里先用最简单字符串）
    # msg = ServiceBusMessage(str(notification_id))
    #
    # with ServiceBusClient.from_connection_string(conn_str) as client:
    #     with client.get_queue_sender(queue_name) as sender:
    #         sender.send_messages(msg)

    try:
        enqueue_notification(notification.id)
    except Exception:
        logging.exception("Failed to enqueue notification")
        notification.status = f"Failed to enqueue notification {notification.id}"
        db.session.commit()
        return render_template('notification.html')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/Registration', methods=['POST', 'GET'])
def registration():
    if request.method == 'POST':
        attendee = Attendee()
        attendee.first_name = request.form['first_name']
        attendee.last_name = request.form['last_name']
        attendee.email = request.form['email']
        attendee.job_position = request.form['job_position']
        attendee.company = request.form['company']
        attendee.city = request.form['city']
        attendee.state = request.form['state']
        attendee.interests = request.form['interest']
        attendee.comments = request.form['message']
        attendee.conference_id = app.config.get('CONFERENCE_ID')

        try:
            db.session.add(attendee)
            db.session.commit()
            session['message'] = 'Thank you, {} {}, for registering!'.format(attendee.first_name, attendee.last_name)
            return redirect('/Registration')
        except Exception:
            logging.exception('Error occured while saving your information')
            return render_template('registration.html')

    else:
        if 'message' in session:
            message = session['message']
            session.pop('message', None)
            return render_template('registration.html', message=message)
        else:
            return render_template('registration.html')


@app.route('/Attendees')
def attendees():
    attendees = Attendee.query.order_by(Attendee.submitted_date).all()
    return render_template('attendees.html', attendees=attendees)


@app.route('/Notifications')
def notifications():
    notifications = Notification.query.order_by(Notification.id).all()
    return render_template('notifications.html', notifications=notifications)


@app.route('/Notification', methods=['POST', 'GET'])
def notification():
    if request.method == 'POST':
        notification = Notification()
        notification.message = request.form['message']
        notification.subject = request.form['subject']
        notification.status = 'Notifications submitted'
        notification.submitted_date = datetime.utcnow()

        try:
            db.session.add(notification)
            db.session.commit()

            # 关键：把 notification.id 推到队列里（异步处理）
            enqueue_notification(notification.id)

            # 可选：你也可以在这里把 status 改成 “Queued”
            notification.status = f"Queued notification {notification.id}"
            db.session.commit()

            return redirect('/Notifications')
        except Exception:
            logging.exception('log unable to save notification')
            return render_template('notification.html')

    else:
        return render_template('notification.html')


def send_email(email, subject, body):
    # 你这里的逻辑目前是反的：if not key -> 还去用 key
    # 正常应该是：有 key 才发送
    if app.config.get('SENDGRID_API_KEY'):
        message = Mail(
            from_email=app.config.get('ADMIN_EMAIL_ADDRESS'),
            to_emails=email,
            subject=subject,
            plain_text_content=body
        )
        sg = SendGridAPIClient(app.config.get('SENDGRID_API_KEY'))
        sg.send(message)
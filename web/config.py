import os
from dotenv import load_dotenv

load_dotenv()

app_dir = os.path.abspath(os.path.dirname(__file__))


class BaseConfig:
    DEBUG = True

    POSTGRES_URL = os.getenv("POSTGRES_URL")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PW = os.getenv("POSTGRES_PW")
    POSTGRES_DB = os.getenv("POSTGRES_DB")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))

    SQLALCHEMY_DATABASE_URI = (
        os.getenv("SQLALCHEMY_DATABASE_URI") or
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PW}@{POSTGRES_URL}/{POSTGRES_DB}"
    )

    CONFERENCE_ID = 1
    SECRET_KEY = "LWd2tzlprdGHCIPHTd4tp5SBFgDszm"

    SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
    SERVICE_BUS_QUEUE_NAME = os.getenv("SERVICE_BUS_QUEUE_NAME")

    ADMIN_EMAIL_ADDRESS = "info@techconf.com"
    SENDGRID_API_KEY = ""
    print("DB HOST:", POSTGRES_URL)
    print("QUEUE:", SERVICE_BUS_QUEUE_NAME)

class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
# wbl-backend/fapi/mail_service.py
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from dotenv import load_dotenv
import os
from fapi.requestdemoMail import RequestDemo_User_HTML_template, RequestDemo_Admin_HTML_template

from fapi.contactMailTemplet import ContactMail_HTML_templete
# from mail_services import mail_conf


# Load environment variables from .env file
load_dotenv()

# Read environment variables directly
mail_conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_FROM=os.getenv('MAIL_FROM'),
    MAIL_PORT=int(os.getenv('MAIL_PORT')),
    MAIL_SERVER=os.getenv('MAIL_SERVER'),
    MAIL_STARTTLS=os.getenv('MAIL_STARTTLS'),
    MAIL_SSL_TLS=os.getenv('MAIL_SSL_TLS') 
)

async def send_reset_password_email(email: EmailStr, token: str):
    reset_link = f"{os.getenv('RESET_PASSWORD_URL')}?token={token}"
    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[email],
        body=f"Click to reset your password: <a href='{reset_link}'>Reset Password</a>",
        subtype="html"
    )
    fm = FastMail(mail_conf)
    await fm.send_message(message)


async def send_request_demo_emails(name: str, email: str, phone: str, address: str = ""):
    user_message = MessageSchema(
        subject="Your Innovapath Demo Request is Confirmed",
        recipients=[email],
        body=RequestDemo_User_HTML_template(name),
        subtype="html"
    )

    admin_message = MessageSchema(
        subject=f"New Demo Request from {name}",
        recipients=["sampath.velupula@gmail.com", "recruiting@whitebox-learning.com","info@innova-path.com"],
        body=RequestDemo_Admin_HTML_template(name, email, phone, address),
        subtype="html"
    )

    fm = FastMail(mail_conf)
    await fm.send_message(user_message)
    await fm.send_message(admin_message)

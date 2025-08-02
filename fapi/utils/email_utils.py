# wbl-backend/fapi/utils/mail_utils.py
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import HTTPException
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from dotenv import load_dotenv

from fapi.db.models import EmailRequest, UserRegistration, ContactForm
from fapi.mail.templets.registerMailTemplet import get_user_email_content, get_admin_email_content
from fapi.mail.templets.contactMailTemplet import ContactMail_HTML_templete
from fapi.mail.templets.requestdemoMail import RequestDemo_User_HTML_template, RequestDemo_Admin_HTML_template

# Load environment variables
load_dotenv()

# ========== SMTP Email Configuration for smtplib ==========
def get_email_config():
    return {
        'from_email': os.getenv('EMAIL_USER'),
        'password': os.getenv('EMAIL_PASS'),
        'smtp_server': os.getenv('SMTP_SERVER'),
        'smtp_port': os.getenv('SMTP_PORT'),
        'to_recruiting_email': os.getenv('TO_RECRUITING_EMAIL'),
        'to_admin_email': os.getenv('TO_ADMIN_EMAIL')
    }

def validate_email_config(config: dict):
    if not all([config['from_email'], config['password'], config['smtp_server'], config['smtp_port']]):
        raise HTTPException(status_code=500, detail="Email server configuration is incomplete.")
    
    admin_emails = [email for email in [config['to_recruiting_email'], config['to_admin_email']] if email]
    if not admin_emails:
        raise HTTPException(status_code=500, detail="No admin email addresses configured.")
    
    return admin_emails

def send_html_email(server, from_email: str, to_emails: list[str], subject: str, html_content: str):
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = ", ".join(to_emails)
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))
    server.sendmail(from_email, to_emails, msg.as_string())

def send_email_to_user(user_email: str, user_name: str, user_phone: str):
    config = get_email_config()
    admin_emails = validate_email_config(config)

    try:
        user_html_content = get_user_email_content(user_name)
        admin_html_content = get_admin_email_content(user_name, user_email, user_phone)

        with smtplib.SMTP(config['smtp_server'], int(config['smtp_port'])) as server:
            server.starttls()
            server.login(config['from_email'], config['password'])

            # Send to user
            send_html_email(
                server=server,
                from_email=config['from_email'],
                to_emails=[user_email],
                subject='Registration Successful - Recruiting Team will Reach Out',
                html_content=user_html_content
            )

            # Send to all admins
            send_html_email(
                server=server,
                from_email=config['from_email'],
                to_emails=admin_emails,
                subject='New User Registration Notification',
                html_content=admin_html_content
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error while sending registration emails: {e}')

def send_contact_emails(first_name: str, last_name: str, email: str, phone: str, message: str):
    config = get_email_config()
    admin_emails = validate_email_config(config)

    html_content = ContactMail_HTML_templete(
        f"{first_name} {last_name}", email, phone, message
    )

    try:
        with smtplib.SMTP(config['smtp_server'], int(config['smtp_port'])) as server:
            server.starttls()
            server.login(config['from_email'], config['password'])

            for admin_email in admin_emails:
                try:
                    send_html_email(
                        server=server,
                        from_email=config['from_email'],
                        to_emails=[admin_email],
                        subject='WBL Contact Lead Generated',
                        html_content=html_content
                    )
                except Exception as e:
                    print(f"Failed to send to {admin_email}: {str(e)}")
                    continue

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail='Error while establishing connection to email server'
        )


# ========== Async Email Configuration for FastMail ==========
fastmail_config = ConnectionConfig(
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_FROM=os.getenv('MAIL_FROM'),
    MAIL_PORT=int(os.getenv('MAIL_PORT')),
    MAIL_SERVER=os.getenv('MAIL_SERVER'),
    MAIL_STARTTLS=os.getenv('MAIL_STARTTLS') == 'True',
    MAIL_SSL_TLS=os.getenv('MAIL_SSL_TLS') == 'True'
)

async def send_reset_password_email(email: EmailStr, token: str):
    reset_link = f"{os.getenv('RESET_PASSWORD_URL')}?token={token}"
    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[email],
        body=f"Click to reset your password: <a href='{reset_link}'>Reset Password</a>",
        subtype="html"
    )
    fm = FastMail(fastmail_config)
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
        recipients=[
            "sampath.velupula@gmail.com",
            "recruiting@whitebox-learning.com",
            "info@innova-path.com"
        ],
        body=RequestDemo_Admin_HTML_template(name, email, phone, address),
        subtype="html"
    )

    fm = FastMail(fastmail_config)
    await fm.send_message(user_message)
    await fm.send_message(admin_message)

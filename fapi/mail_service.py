from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from config import conf  # Import the Settings object from config.py

# Use the settings object from config.py to initialize ConnectionConfig
mail_conf = ConnectionConfig(
    MAIL_USERNAME=conf.MAIL_USERNAME,
    MAIL_PASSWORD=conf.MAIL_PASSWORD,
    MAIL_FROM=conf.MAIL_FROM,
    MAIL_PORT=conf.MAIL_PORT,
    MAIL_SERVER=conf.MAIL_SERVER,
    MAIL_STARTTLS=conf.MAIL_STARTTLS,  # Use MAIL_STARTTLS instead of MAIL_TLS
    MAIL_SSL_TLS=conf.MAIL_SSL_TLS,  # Adjusted to match the configuration name
)

async def send_reset_password_email(email: EmailStr, token: str):
    reset_link = f"http://localhost:3000/reset-password?token={token}"
    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[email],
        body=f"Click on the link to reset your password: {reset_link}",
        subtype="html"
    )
    fm = FastMail(mail_conf)
    await fm.send_message(message)

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from config import conf  # Import the Settings object from config.py
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Use the settings object from config.py to initialize ConnectionConfig
# mail_conf = ConnectionConfig(
#     MAIL_USERNAME=conf.MAIL_USERNAME,
#     MAIL_PASSWORD=conf.MAIL_PASSWORD,
#     MAIL_FROM=conf.MAIL_FROM,
#     MAIL_PORT=conf.MAIL_PORT,
#     MAIL_SERVER=conf.MAIL_SERVER,
#     MAIL_STARTTLS=conf.MAIL_STARTTLS,  # Use MAIL_STARTTLS instead of MAIL_TLS
#     MAIL_SSL_TLS=conf.MAIL_SSL_TLS,  # Adjusted to match the configuration name
# )


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
    # reset_link = f"http://localhost:3000/reset-password?token={token}"
    reset_link = f"{os.getenv('RESET_PASSWORD_URL')}?token={token}"
    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[email],
        # body=f"Click on the link to reset your password: {reset_link}",
        body=f"Click to reset your password: <a href='{reset_link}'>Reset Password</a>",
        subtype="html"
    )
    fm = FastMail(mail_conf)
    await fm.send_message(message)

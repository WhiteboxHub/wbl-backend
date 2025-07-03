# wbl-backend/fapi/mail_service.py
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from dotenv import load_dotenv
import os
from fapi.requestdemoMail import RequestDemo_User_HTML_template, RequestDemo_Admin_HTML_template

from fapi.contactMailTemplet import ContactMail_HTML_templete

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
        recipients=["hemanthdobriyal@gmail.com", "abhirohith516@gmail.com"],
        body=RequestDemo_Admin_HTML_template(name, email, phone, address),
        subtype="html"
    )

    fm = FastMail(mail_conf)
    await fm.send_message(user_message)
    await fm.send_message(admin_message)




# async def lead_generation_mail( user_name: str,user_email: str,html_content):
#     mail_conf = ConnectionConfig(
#     MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
#     MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
#     MAIL_FROM=os.getenv('MAIL_FROM'),
#     MAIL_PORT=int(os.getenv('MAIL_PORT')),
#     MAIL_SERVER=os.getenv('MAIL_SERVER'),
#     MAIL_STARTTLS=True,
#     MAIL_SSL_TLS=False,
#     USE_CREDENTIALS=True
# )
#     # async def send_email_to_user():
#     from_email = os.getenv('EMAIL_USER')
#     to_recruiting_email = os.getenv('TO_RECRUITING_EMAIL')
#     to_admin_email = os.getenv('ADMIN_MAIL')
#     print(to_recruiting_email,to_admin_email,"-"*100)

#     # Email content for the user
#     user_html_content = f"""
#     <html>
#         <body>
#             <p>Dear {user_name},</p>
#             <p>Thank you for registering with us. We are pleased to inform you that our recruiting team will reach out to you shortly.</p>
#             <p>Best regards,<br>Recruitment Team</p>
#         </body>
#     </html>
#     """

#     # Email content for the admin
#     admin_html_content = f"""
#     <html>
#         <body>
#             <p>Hello Admin,</p>
#             <p>A new user has registered on the website. Please review their details and provide access.</p>
#             <p><strong>User Details:</strong></p>
#             <ul>
#                 <li>Name: {user_name}</li>
#                 <li>Email: {user_email}</li>
#             </ul>
#             <p>Best regards,<br>System Notification</p>
#         </body>
#     </html>
#     """

#     # Prepare message schemas
#     # user_message = MessageSchema(
#     #     subject="Registration Successful - Recruiting Team will Reach Out",
#     #     recipients=[user_email],
#     #     body=user_html_content,
#     #     subtype="html"
#     # )

#     admin_message = MessageSchema(
#         subject="New User Registration Notification",
#         recipients=[to_recruiting_email, to_admin_email],
#         body=html_content,
#         subtype="html"
#     )

#     # Send the emails
#     fm = FastMail(mail_conf)
#     try:
#         print(f"sending maile to {to_recruiting_email} ,{to_admin_email}")
#         # await fm.send_message(user_message)
#         await fm.send_message(admin_message)
#         print(f"sending maile to {to_recruiting_email} ,{to_admin_email}")

#     except Exception as e:
#         from fastapi import HTTPException
#         raise HTTPException(status_code=500, detail=f"Error while sending emails: {e}")
import os
import smtplib
from fapi.models import EmailRequest, UserRegistration, ContactForm
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import HTTPException
from fapi.registerMailTemplet import get_user_email_content, get_admin_email_content
from fapi.contactMailTemplet import ContactMail_HTML_templete
from fapi.registerMailTemplet import get_user_email_content, get_admin_email_content
from fapi.contactMailTemplet import ContactMail_HTML_templete
from fapi.utils.auth_utils import md5_hash, verify_md5_hash, hash_password, verify_reset_token





def send_html_email(server, from_email: str, to_email: str, subject: str, html_content: str):
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))
    server.sendmail(from_email, to_email, msg.as_string())


def send_email_to_user(user_email: str, user_name: str, user_phone: str):
    from_email = os.getenv('EMAIL_USER')
    password = os.getenv('EMAIL_PASS')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    to_recruiting_email = os.getenv('TO_RECRUITING_EMAIL')
    to_admin_email = os.getenv('TO_ADMIN_EMAIL')

    try:
        user_html_content = get_user_email_content(user_name)
        admin_html_content = get_admin_email_content(user_name, user_email, user_phone)

        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(from_email, password)

        send_html_email(
            server,
            from_email=from_email,
            to_email=user_email,
            subject='Registration Successful - Recruiting Team will Reach Out',
            html_content=user_html_content
        )

        for admin_email in filter(None, [to_recruiting_email, to_admin_email]):
            send_html_email(
                server,
                from_email=from_email,
                to_email=admin_email,
                subject='New User Registration Notification',
                html_content=admin_html_content
            )

        server.quit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error while sending registration emails: {e}')


def send_contact_emails(first_name: str, last_name: str, email: str, phone: str, message: str):
    from_email = os.getenv('EMAIL_USER')
    password = os.getenv('EMAIL_PASS')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    to_recruiting_email = os.getenv('TO_RECRUITING_EMAIL')
    to_admin_email = os.getenv('TO_ADMIN_EMAIL')

    html_content = ContactMail_HTML_templete(
        f"{first_name} {last_name}", email, phone, message
    )

    try:
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(from_email, password)

        for contact_email in filter(None, [to_recruiting_email, to_admin_email]):
            send_html_email(
                server=server,
                from_email=from_email,
                to_email=contact_email,
                subject='WBL Contact Lead Generated',
                html_content=html_content
            )

        server.quit()

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail='Error while sending the contact email to recruiting teams')


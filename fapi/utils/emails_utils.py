import os
import smtplib
from fapi.models import EmailRequest, UserRegistration, ContactForm
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import HTTPException
from fapi.registerMailTemplet import get_user_email_content, get_admin_email_content
from fapi.contactMailTemplet import ContactMail_HTML_templete
from fapi.utils.auth_utils import md5_hash, verify_md5_hash, hash_password, verify_reset_token

# Email configuration
def get_email_config():
    """Load and return all email configuration"""
    return {
        'from_email': os.getenv('EMAIL_USER'),
        'password': os.getenv('EMAIL_PASS'),
        'smtp_server': os.getenv('SMTP_SERVER'),
        'smtp_port': os.getenv('SMTP_PORT'),
        'to_recruiting_email': os.getenv('TO_RECRUITING_EMAIL'),
        'to_admin_email': os.getenv('TO_ADMIN_EMAIL')
    }

def validate_email_config(config: dict):
    """Validate email configuration and return admin emails"""
   
    if not all([config['from_email'], config['password'], config['smtp_server'], config['smtp_port']]):
        raise HTTPException(status_code=500, detail="Email server configuration is incomplete.")
    
    admin_emails = [email for email in [config['to_recruiting_email'], config['to_admin_email']] if email]
    if not admin_emails:
        raise HTTPException(status_code=500, detail="No admin email addresses configured.")
    
    return admin_emails

def send_html_email(server, from_email: str, to_emails: list[str], subject: str, html_content: str):
    """Send HTML email to one or more recipients"""
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = ", ".join(to_emails)  
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))
    server.sendmail(from_email, to_emails, msg.as_string())


def send_email_to_user(user_email: str, user_name: str, user_phone: str):
    """Send registration emails to user and admins"""
    config = get_email_config()
    admin_emails = validate_email_config(config)
    print(f"Admin emails: {admin_emails}")

    try:
    
        user_html_content = get_user_email_content(user_name)
        admin_html_content = get_admin_email_content(user_name, user_email, user_phone)

      
        with smtplib.SMTP(config['smtp_server'], int(config['smtp_port'])) as server:
            server.starttls()
            server.login(config['from_email'], config['password'])

            # Send to user
            send_html_email(
                server,
                from_email=config['from_email'],
                to_emails=[user_email],
                subject='Registration Successful - Recruiting Team will Reach Out',
                html_content=user_html_content
            )

            # Send to all admins
            send_html_email(
                server,
                from_email=config['from_email'],
                to_emails=admin_emails,
                subject='New User Registration Notification',
                html_content=admin_html_content
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error while sending registration emails: {e}')

def send_contact_emails(first_name: str, last_name: str, email: str, phone: str, message: str):
    """Send contact form emails to admins"""
    config = get_email_config()
    admin_emails = validate_email_config(config)
    print(f"Attempting to send to admin emails: {admin_emails}")

  
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
                    print(f"Successfully sent to: {admin_email}")
                except Exception as e:
                    print(f"Failed to send to {admin_email}: {str(e)}")
                    continue

    except Exception as e:
        print(f"SMTP connection error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail='Error while establishing connection to email server'
        )
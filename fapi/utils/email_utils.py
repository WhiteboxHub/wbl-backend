# wbl-backend/fapi/utils/mail_utils.py
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import HTTPException
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from typing import List, Dict
from pydantic import EmailStr
from dotenv import load_dotenv

from fapi.db.schemas import UserRegistration, EmailRequest, ContactForm
from fapi.mail.templets.registerMailTemplet import get_user_email_content, get_admin_email_content
from fapi.mail.templets.contactMailTemplet import ContactMail_HTML_templete
from fapi.mail.templets.professional_email_templates import get_professional_user_email_content, get_professional_admin_email_content, get_professional_contact_email_content
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
    
    raw_emails = [config['to_recruiting_email'], config['to_admin_email']]
    admin_emails = []
    for raw in raw_emails:
        if raw:
            # Split by comma and strip whitespace
            emails = [e.strip() for e in raw.split(',') if e.strip()]
            admin_emails.extend(emails)
            
    if not admin_emails:
        raise HTTPException(status_code=500, detail="No admin email addresses configured.")
    
    return list(set(admin_emails))  # Remove duplicates

def send_html_email(server, from_email: str, to_emails: list[str], subject: str, html_content: str, text_content: str = None):
    from email.utils import formatdate, make_msgid
    
    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')
    msg['From'] = from_email
    
    # Send to all recipients
    if to_emails:
        msg['To'] = ", ".join(to_emails)
    else:
        msg['To'] = from_email
        
    # Standard MIME structure for better compatibility
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid()
    msg['MIME-Version'] = '1.0'

    # Attach parts: plain text first, then HTML (standard multipart/alternative)
    alt_text = "Weekly Marketing Report. Please use an HTML compatible email client."
    p_text = text_content if text_content else alt_text
    
    part1 = MIMEText(p_text, 'plain', 'utf-8')
    part2 = MIMEText(html_content, 'html', 'utf-8')
    
    msg.attach(part1)
    msg.attach(part2)
    
    try:
        raw_msg = msg.as_string()
        # The envelope recipients should be the list of emails
        server.sendmail(from_email, to_emails, raw_msg)
    except Exception as e:
        print(f"ERROR: send_html_email failed: {str(e)}")
        raise e

def send_email_to_user(user_email: str, user_name: str, user_phone: str):
    config = get_email_config()
    admin_emails = validate_email_config(config)

    try:
        user_html_content = get_professional_user_email_content(user_name)
        admin_html_content = get_professional_admin_email_content(user_name, user_email, user_phone)

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

    html_content = get_professional_contact_email_content(
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

    config = get_email_config()
    admin_emails = validate_email_config(config)
    
    admin_message = MessageSchema(
        subject=f"New Demo Request from {name}",
        recipients=admin_emails,
        body=RequestDemo_Admin_HTML_template(name, email, phone, address),
        subtype="html"
    )

    fm = FastMail(fastmail_config)
    await fm.send_message(user_message)
    await fm.send_message(admin_message)

async def send_referral_emails(
    referrer_name: str,
    referrer_email: str, 
    referrer_phone: str,
    candidate_name: str,
    candidate_email: str,
    candidate_phone: str,
    candidate_workstatus: str,
    candidate_address: str,
    additional_notes: str
):
    """Send referral notification emails to admin recipients"""
    
    # Debug logging to see what data we're receiving
    print(f"DEBUG - Email function received:")
    print(f"  Referrer: {referrer_name} ({referrer_email}) - {referrer_phone}")
    print(f"  Candidate: {candidate_name} ({candidate_email}) - {candidate_phone}")
    print(f"  Work Status: {candidate_workstatus}")
    print(f"  Address: {candidate_address}")
    print(f"  Notes: {additional_notes}")
    
    # Create HTML email content for referral notification
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #4A6CF7; border-bottom: 2px solid #4A6CF7; padding-bottom: 10px;">
                 New Referral Submission - AIML Training Program
            </h2>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Referrer Information</h3>
                <p><strong>Name:</strong> {referrer_name}</p>
                <p><strong>Email:</strong> {referrer_email}</p>
                <p><strong>Phone:</strong> {referrer_phone}</p>
            </div>
            
            <div style="background-color: #e8f4fd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Referred Candidate Information</h3>
                <p><strong>Name:</strong> {candidate_name}</p>
                <p><strong>Email:</strong> {candidate_email}</p>
                <p><strong>Phone:</strong> {candidate_phone}</p>
                <p><strong>Work Status:</strong> {candidate_workstatus}</p>
                <p><strong>Address:</strong> {candidate_address}</p>
            </div>
            
            <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Additional Notes</h3>
                <p>{additional_notes}</p>
            </div>
            
            <div style="margin-top: 30px; padding: 20px; background-color: #d4edda; border-radius: 8px;">
                <p style="margin: 0; font-weight: bold; color: #155724;">
                     Next Steps: Please reach out to the referred candidate to discuss the AIML training program and enrollment process.
                </p>
            </div>
            
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
            <p style="font-size: 12px; color: #666; text-align: center;">
                This referral was submitted through the Whitebox Learning Refer and Earn program.
            </p>
        </div>
    </body>
    </html>
    """
    
    config = get_email_config()
    admin_emails = validate_email_config(config)
    
    # Send email to specified recipients
    admin_message = MessageSchema(
        subject=f" New AIML Program Referral from {referrer_name}",
        recipients=admin_emails,
        body=html_content,
        subtype="html"
    )
    
    fm = FastMail(fastmail_config)
    await fm.send_message(admin_message)


async def send_onboarding_documents_email(
    candidate_name: str,
    candidate_email: str,
    candidate_phone: str,
    file_paths: List[str]
):
    """Send onboarding documents to recruiters as attachments"""
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 10px;">
                 New Candidate Onboarding Documents
            </h2>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #1e40af; margin-top: 0;">Candidate Information</h3>
                <p><strong>Name:</strong> {candidate_name}</p>
                <p><strong>Email:</strong> {candidate_email}</p>
                <p><strong>Phone:</strong> {candidate_phone}</p>
            </div>
            
            <div style="margin-top: 30px; padding: 20px; background-color: #fef3c7; border-radius: 8px; border-left: 4px solid #f59e0b;">
                <p style="margin: 0; font-weight: bold; color: #92400e;">
                    Action Required:
                </p>
                <p style="margin: 5px 0 0 0;">
                    Please review the attached documents. If everything is in order, go to the Admin Dashboard and set the "Agreement" flag to **Yes** for this candidate to grant them dashboard access.
                </p>
            </div>
            
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
            <p style="font-size: 12px; color: #666; text-align: center;">
                Whitebox Learning - Candidate Onboarding System
            </p>
        </div>
    </body>
    </html>
    """
    
    config = get_email_config()
    admin_emails = validate_email_config(config)
    
    message = MessageSchema(
        subject=f"Onboarding Documents: {candidate_name}",
        recipients=admin_emails,
        body=html_content,
        subtype="html",
        attachments=file_paths
    )
    
    fm = FastMail(fastmail_config)
    await fm.send_message(message)


async def send_agreement_signed_email(
    candidate_name: str,
    candidate_email: str,
    signature: str,
    notes: str
):
    """Notify recruiters that a candidate has signed the agreement"""
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #10b981; border-bottom: 2px solid #10b981; padding-bottom: 10px;">
                 Agreement Signed & Pending Review
            </h2>
            
            <div style="background-color: #f0fdf4; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #065f46; margin-top: 0;">Candidate Details</h3>
                <p><strong>Name:</strong> {candidate_name}</p>
                <p><strong>Email:</strong> {candidate_email}</p>
                <p><strong>Signature:</strong> <span style="font-family: 'Brush Script MT', cursive; font-size: 20px;">{signature}</span></p>
            </div>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #10b981;">
                <p><strong>Submission Details:</strong></p>
                <p>{notes}</p>
            </div>

            <div style="margin-top: 30px; padding: 20px; background-color: #fef3c7; border-radius: 8px;">
                <p style="margin: 0; font-weight: bold; color: #92400e;">
                    Final Step:
                </p>
                <p style="margin: 5px 0 0 0;">
                    The candidate has completed all onboarding steps. Please verify the documents and signature. If satisfied, change their status to <strong>'Agreement: Yes'</strong> to grant them full access.
                </p>
            </div>
            
            <p style="font-size: 12px; color: #666; text-align: center; margin-top: 30px;">
                Whitebox Learning - Automated Onboarding System
            </p>
        </div>
    </body>
    </html>
    """
    
    config = get_email_config()
    admin_emails = validate_email_config(config)
    
    message = MessageSchema(
        subject=f" Agreement Signed: {candidate_name}",
        recipients=admin_emails,
        body=html_content,
        subtype="html"
    )
    
    fm = FastMail(fastmail_config)
    await fm.send_message(message)

async def send_consolidated_onboarding_email(
    candidate_name: str,
    candidate_email: str,
    candidate_phone: str,
    signature: str,
    notes: str,
    drive_link: str,
    file_paths: List[str] = None
):
    """Notify recruiters with a single consolidated onboarding email"""
    
    html_content = f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7fa; padding: 20px;">
        <div style="max-width: 700px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border: 1px solid #e1e8ed;">
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 35px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 26px; letter-spacing: 1px; font-weight: 700;">Onboarding Complete</h1>
                <p style="color: #d1d5db; margin: 8px 0 0 0; font-size: 16px;">New Candidate Application & Agreement Received</p>
            </div>

            <div style="padding: 35px;">
                <!-- Candidate Info -->
                <div style="background-color: #f8fafc; border-radius: 10px; padding: 20px; margin-bottom: 30px; border-left: 5px solid #3b82f6;">
                    <h3 style="color: #1e40af; margin-top: 0; margin-bottom: 15px; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; display: flex; align-items: center;">
                         Candidate Information
                    </h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 5px 0; color: #64748b; width: 100px;"><strong>Name:</strong></td><td style="padding: 5px 0;">{candidate_name}</td></tr>
                        <tr><td style="padding: 5px 0; color: #64748b;"><strong>Email:</strong></td><td style="padding: 5px 0;">{candidate_email}</td></tr>
                        <tr><td style="padding: 5px 0; color: #64748b;"><strong>Phone:</strong></td><td style="padding: 5px 0;">{candidate_phone}</td></tr>
                    </table>
                </div>

                <!-- Terms and Conditions -->
                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 30px; margin-bottom: 30px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);">
                    <h3 style="color: #1e40af; margin-top: 0; margin-bottom: 20px; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">📜 Placement Terms & Conditions</h3>
                    <div style="font-size: 14px; color: #4b5563; line-height: 1.7;">
                        <h4 style="color: #1f2937; font-size: 16px; margin-bottom: 12px; margin-top: 0;">Payment Guidelines and Placement Terms</h4>
                        <p>This document outlines the payment structure, placement fees, and re-support terms for candidates enrolled with our training and placement services, with a focus on IT roles including AI and ML positions.</p>
                        
                        <p><strong>1. Post Placement Fees</strong><br/>
                        After successful placement, a placement fee of <strong>13%</strong> from your offered annual salary will be applicable.</p>
                        
                        <p><strong>2. Payment Method and Installments</strong><br/>
                        The post placement fee may be paid in three installments using postpaid checks.</p>
                        <ul style="padding-left: 20px;">
                            <li>All checks must be handed over before background check clearance and before onboarding date.</li>
                            <li>The first check will be deposited before the candidate's job start date.</li>
                            <li>All remaining checks will be deposited within two months from the candidate's start date.</li>
                        </ul>
                        
                        <div style="background-color: #f1f5f9; padding: 15px; border-radius: 8px; margin: 15px 0;">
                            <p style="margin: 0; font-weight: bold; color: #334155;">Illustration:</p>
                            <p style="margin: 5px 0;">If offer received of USD 150,000, then 13% of 150,000 that is 19,500 is split into three installments:</p>
                            <ul style="margin-bottom: 0; padding-left: 20px;">
                                <li>First Installment: $6,500, payable after BGV and before Onboarding date.</li>
                                <li>Second Installment: $6,500, payable after receiving your first paycheck.</li>
                                <li>Third Installment: $6,500, payable after receiving your second paycheck.</li>
                            </ul>
                        </div>
                        
                        <p><strong>3. Support Period and Re-Placement Policy</strong><br/>
                        We provide placement support for a period of one month from the candidate's job start date. If a candidate is terminated or laid off within the first two months of the job start date, we will provide re-placement support at no additional cost.</p>
                        
                        <div style="margin-top: 30px; padding: 25px; background-color: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 12px; position: relative;">
                            <div style="position: absolute; top: -12px; left: 20px; background-color: #10b981; color: white; padding: 2px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase;">Digitally Signed</div>
                            <p style="margin: 0; font-style: italic; color: #166534; font-size: 13px;">
                                "I have read, understood, and agree to the Placement Terms and Conditions outlined above. I acknowledge my responsibility to fulfill the placement fee obligations as specified."
                            </p>
                            <div style="margin-top: 20px; border-top: 1px solid #d1fae5; padding-top: 15px; display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <span style="display: block; font-size: 11px; color: #059669; text-transform: uppercase; font-weight: bold; margin-bottom: 4px;">Adaptive Signature</span>
                                    <span style="font-family: 'Brush Script MT', cursive; font-size: 28px; color: #065f46; border-bottom: 1px solid #059669; padding: 0 10px;">{signature}</span>
                                </div>
                                <div style="text-align: right;">
                                    <span style="display: block; font-size: 10px; color: #6b7280;">Timestamp & Record</span>
                                    <span style="font-size: 11px; color: #374151; font-family: monospace;">{notes.split('at ')[1] if 'at ' in notes else 'Record ID: ' + signature[:8]}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {f'''
                <!-- Cloud Documents Link -->
                <div style="background-color: #eff6ff; border-radius: 10px; padding: 25px; margin-bottom: 30px; border: 2px dashed #3b82f6; text-align: center;">
                    <h3 style="color: #1e40af; margin-top: 0; margin-bottom: 10px;">📂 Cloud Documents</h3>
                    <p style="margin: 0 0 20px 0; color: #4b5563;">Candidate verification documents have been securely uploaded.</p>
                    <a href="{drive_link}" style="display: inline-block; padding: 12px 28px; background-color: #3b82f6; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; transition: all 0.3s ease; box-shadow: 0 4px 6px rgba(59, 130, 246, 0.2);">
                        Access Google Drive Folder
                    </a>
                </div>
                ''' if "http" in drive_link else ""}

                <div style="padding: 20px; background-color: #fffbeb; border-radius: 10px; border: 1px solid #fde68a; display: flex; align-items: flex-start; gap: 15px;">
                    <span style="font-size: 24px;"></span>
                    <div>
                        <p style="margin: 0; font-weight: bold; color: #92400e; font-size: 15px;">Final Approval Required</p>
                        <p style="margin: 5px 0 0 0; font-size: 13px; color: #b45309; line-height: 1.5;">
                            Please verify the documents and signature. Once verified, set <strong>Agreement: Yes</strong> in the Admin Dashboard to activate this candidate profile.
                        </p>
                    </div>
                </div>
            </div>

            <div style="background-color: #f9fafb; padding: 25px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="font-size: 12px; color: #9ca3af; margin: 0;">&copy; 2026 Whitebox Learning • Automated Onboarding System</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    config = get_email_config()
    admin_emails = validate_email_config(config)
    
    message = MessageSchema(
        subject=f" Complete Onboarding: {candidate_name}",
        recipients=admin_emails,
        body=html_content,
        subtype="html",
        attachments=file_paths if file_paths else []
    )
    
    fm = FastMail(fastmail_config)
    await fm.send_message(message)


async def send_document_approval_email(candidate_email: str, candidate_name: str):
    """Notify the candidate that their onboarding/agreement documents have been approved"""
    html_content = f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7fa; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border: 1px solid #e1e8ed;">
            <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 35px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 26px; letter-spacing: 1px; font-weight: 700;">Documents Approved!</h1>
                <p style="color: #d1fae5; margin: 8px 0 0 0; font-size: 16px;">Welcome to the Whitebox Learning Dashboard</p>
            </div>

            <div style="padding: 35px;">
                <h2 style="color: #065f46; margin-top: 0; font-size: 20px;">Hello {candidate_name},</h2>
                <p style="font-size: 16px; color: #4b5563;">
                    Great news! Our team has completed the review of your onboarding documents and signed agreement. We are pleased to inform you that your documents have been <strong>approved</strong>.
                </p>
                <p style="font-size: 16px; color: #4b5563;">
                    Your candidate profile is now fully active, and you have been granted access to your personalized candidate dashboard.
                </p>

                <div style="background-color: #f0fdf4; border-radius: 10px; padding: 20px; margin: 30px 0; border-left: 5px solid #10b981;">
                    <h3 style="color: #065f46; margin-top: 0; margin-bottom: 10px; font-size: 16px;">🚀 Next Steps</h3>
                    <ul style="margin: 0; padding-left: 20px; color: #374151; font-size: 15px; line-height: 1.7;">
                        <li>Log in to your Whitebox Learning candidate account.</li>
                        <li>Navigate to your dashboard to view your schedule and materials.</li>
                        <li>Stay tuned for updates from our recruiting team.</li>
                    </ul>
                </div>

                <div style="text-align: center; margin: 35px 0;">
                    <a href="http://localhost:3000/auth/signin" style="display: inline-block; padding: 12px 30px; background-color: #10b981; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 6px rgba(16, 185, 129, 0.2);">
                        Go to Candidate Dashboard
                    </a>
                </div>

                <p style="font-size: 15px; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 20px;">
                    If you have any questions or require immediate support, please contact the Recruiting Team at <strong>recruiting@whitebox-learning.com</strong> or call us at <strong>+1 925-557-1053</strong>.
                </p>
            </div>

            <div style="background-color: #f9fafb; padding: 25px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="font-size: 12px; color: #9ca3af; margin: 0;">&copy; 2026 Whitebox Learning • Candidate Placement System</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send directly to the candidate's email
    message = MessageSchema(
        subject="Your Onboarding Documents have been Approved!",
        recipients=[candidate_email],
        body=html_content,
        subtype="html"
    )
    
    fm = FastMail(fastmail_config)
    await fm.send_message(message)


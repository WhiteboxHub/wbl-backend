import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import HTTPException
from mail_services import mail_conf 
from fastapi_mail import FastMail, MessageSchema
from pydantic import EmailStr



user_html_content = get_user_email_content(user_name)
admin_html_content = get_admin_email_content(user_name, user_email, user_phone)



# Send email to the user
user_msg = MIMEMultipart()
user_msg['From'] = from_email
user_msg['To'] = user_email
user_msg['Subject'] = 'Registration Successful - Recruiting Team will Reach Out'
user_msg.attach(MIMEText(user_html_content, 'html'))
server.sendmail(from_email, user_email, user_msg.as_string())
        
        # List of admin emails to notify

        # for admin_emails in [to_recruiting_email, to_admin_email]:
for admin_emails in filter(None, [to_recruiting_email, to_admin_email]):



            # Send email to the admin
    admin_msg = MIMEMultipart()
    admin_msg['From'] = from_email  
    admin_msg['To'] = admin_emails
    admin_msg['Subject'] = 'New User Registration Notification'
    admin_msg.attach(MIMEText(admin_html_content, 'html'))
    server.sendmail(from_email, admin_emails, admin_msg.as_string())

            # Send email to the admin
    admin_msg = MIMEMultipart()
    admin_msg['From'] = from_email
    admin_msg['To'] = to_admin_email
    admin_msg['Subject'] = 'New User Registration Notification'
    admin_msg.attach(MIMEText(admin_html_content, 'html'))
    server.sendmail(from_email, to_admin_email, admin_msg.as_string())

        # Close the server
server.quit()


# except Exception as e:
#     raise HTTPException(status_code=500, detail=f'Error while sending emails: {e}')


# def send_html_email(server, from_email, to_email, subject, html_content):
#     msg = MIMEMultipart()
#     msg['From'] = from_email
#     msg['To'] = to_email
#     msg['Subject'] = subject
#     msg.attach(MIMEText(html_content, 'html'))
#     server.sendmail(from_email, to_email, msg.as_string())




async def contact(user: ContactForm):

    await user_contact(
        # name=f"{user.firstName} {user.lastName}",
        name=f"{user.firstName} {user.lastName}",
        email=user.email,
        phone=user.phone,
        message=user.message        
        )

    def sendEmail(email):
        from_Email = os.getenv('EMAIL_USER')
        password = os.getenv('EMAIL_PASS')
        to_email = email
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = os.getenv('SMTP_PORT')
        html_content = ContactMail_HTML_templete(f"{user.firstName} {user.lastName}",user.email,user.phone,user.message)
        msg = MIMEMultipart()
        msg['From'] = from_Email
        msg['To'] = to_email
        msg['Subject'] = 'WBL Contact lead generated'
        msg.attach(MIMEText(html_content, 'html'))
        try:
            # server = smtplib.SMTP('smtp.gmail.com',587)
            server = smtplib.SMTP(smtp_server, int(smtp_port))
            server.starttls()
            server.login(from_Email,password)
            text = msg.as_string()
            server.sendmail(from_Email,to_email,text)
            server.quit()
        except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail='Erro while sending the mail to recruiting teams')
    

   
    sendEmail(os.getenv('TO_RECRUITING_EMAIL'))
    sendEmail(os.getenv('TO_ADMIN_EMAIL'))

    return {"detail": "Message Sent Successfully"}
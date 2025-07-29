# Email content for the user

from datetime import date

def get_user_email_content(user_name: str) -> str:
    return f"""
    <html>
        <body>
            <p>Dear {user_name},</p>
            <p>Thank you for registering with us. We are pleased to inform you that our recruiting team will reach out to you shortly.</p>
            <p>Best regards,<br>Recruitment Team</p>
        </body>
    </html>
    """

# Email content for the admin

def get_admin_email_content(user_name: str, user_email: str, user_phone: str) -> str:
    return f"""
    <html>
        <body>
            <p>Hello Admin,</p>
            <p>A new user has registered on the website. Please review their details and provide access.</p>
            <p><strong>User Details:</strong></p>
            <ul>
                <li>Name: {user_name}</li>
                <li>Email: {user_email}</li>
                <li>Phone: {user_phone}</li>
            </ul>
            <p>Best regards,<br>System Notification</p>
        </body>
    </html>
    """

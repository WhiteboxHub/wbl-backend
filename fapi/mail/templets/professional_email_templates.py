# Professional Email Templates for WBL Backend - Weekly Report Style
from datetime import date

def get_professional_user_email_content(user_name: str) -> str:
    """Professional user registration welcome email in weekly report style"""
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f9f9f9;
                color: #333;
                padding: 20px;
                margin: 0;
            }}
            .email-container {{
                max-width: 900px;
                margin: 0 auto;
                background: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #ffffff;
                text-align: center;
                padding: 25px;
                border-radius: 8px 8px 0 0;
                margin: -30px -30px 30px -30px;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: bold;
            }}
            .header .subtitle {{
                margin: 5px 0 0 0;
                font-size: 14px;
                opacity: 0.9;
            }}
            .welcome-section {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .welcome-section h2 {{
                color: #2c3e50;
                margin-bottom: 15px;
            }}
            .welcome-message {{
                font-size: 16px;
                line-height: 1.6;
                color: #555;
                margin-bottom: 20px;
            }}
            .user-info {{
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 20px;
                margin: 20px 0;
            }}
            .user-info h3 {{
                color: #2c3e50;
                margin-top: 0;
                margin-bottom: 15px;
            }}
            .user-info p {{
                margin: 8px 0;
                font-size: 15px;
            }}
            .next-steps {{
                background-color: #d1ecf1;
                border: 1px solid #bee5eb;
                border-radius: 5px;
                padding: 15px;
                margin: 20px 0;
                text-align: center;
            }}
            .next-steps strong {{
                color: #0c5460;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #777;
                font-size: 14px;
            }}
            .contact-info {{
                background-color: #e9ecef;
                border-radius: 5px;
                padding: 15px;
                margin: 15px 0;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h1>🎉 Welcome to Innovapath!</h1>
                <div class="subtitle">Your Journey Starts Here</div>
            </div>

            <div class="welcome-section">
                <h2>Hello {user_name}!</h2>
                <div class="welcome-message">
                    <p>Thank you for joining the Innovapath community! We're excited to help you advance your career in technology.</p>
                    <p>Our recruitment team will reach out to you within 24 hours to discuss your goals and explore opportunities that match your profile.</p>
                </div>
            </div>

            <div class="user-info">
                <h3>📋 Your Registration Details</h3>
                <p><strong>Name:</strong> {user_name}</p>
                <p><strong>Registration Date:</strong> {date.today().strftime('%B %d, %Y')}</p>
                <p><strong>Status:</strong> <span style="color: #28a745; font-weight: bold;">Active</span></p>
            </div>

            <div class="next-steps">
                <strong>⚡ What happens next?</strong><br>
                Our team will review your profile and contact you with personalized opportunities.
            </div>

            <div class="contact-info">
                <p><strong>📞 Need immediate assistance?</strong></p>
                <p>Contact us at: <strong>recruiting@whitebox-learning.com</strong></p>
            </div>

            <div class="footer">
                <p>Best regards,<br><strong>The Innovapath Recruitment Team</strong></p>
                <p>Empowering careers through innovative learning solutions</p>
            </div>
        </div>
    </body>
    </html>
    """

def get_professional_admin_email_content(user_name: str, user_email: str, user_phone: str) -> str:
    """Professional admin notification email in weekly report style"""
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f9f9f9;
                color: #333;
                padding: 20px;
                margin: 0;
            }}
            .email-container {{
                max-width: 900px;
                margin: 0 auto;
                background: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                color: #ffffff;
                text-align: center;
                padding: 25px;
                border-radius: 8px 8px 0 0;
                margin: -30px -30px 30px -30px;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: bold;
            }}
            .header .subtitle {{
                margin: 5px 0 0 0;
                font-size: 14px;
                opacity: 0.9;
            }}
            .alert-section {{
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 5px;
                padding: 20px;
                margin: 20px 0;
                text-align: center;
            }}
            .alert-section strong {{
                color: #856404;
                font-size: 16px;
            }}
            .user-details {{
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 25px;
                margin: 20px 0;
            }}
            .user-details h3 {{
                color: #2c3e50;
                margin-top: 0;
                margin-bottom: 20px;
                font-size: 18px;
            }}
            .details-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }}
            .details-table th {{
                background-color: #a3d9a5;
                color: #000;
                font-weight: bold;
                padding: 12px;
                text-align: left;
                border: 1px solid #ddd;
                width: 30%;
            }}
            .details-table td {{
                padding: 12px;
                border: 1px solid #ddd;
                background-color: #ffffff;
            }}
            .action-required {{
                background-color: #d1ecf1;
                border: 1px solid #bee5eb;
                border-radius: 5px;
                padding: 20px;
                margin: 20px 0;
                text-align: center;
            }}
            .action-required h4 {{
                color: #0c5460;
                margin-top: 0;
                margin-bottom: 10px;
            }}
            .action-required ul {{
                text-align: left;
                display: inline-block;
                margin: 0;
                padding-left: 20px;
            }}
            .action-required li {{
                margin: 5px 0;
                color: #0c5460;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #777;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h1>🚨 New User Registration Alert</h1>
                <div class="subtitle">Action Required - Contact Within 24 Hours</div>
            </div>

            <div class="alert-section">
                <strong>⚡ PRIORITY: New user registration requires immediate attention!</strong>
            </div>

            <div class="user-details">
                <h3>👤 New User Registration Details</h3>
                <table class="details-table">
                    <tr>
                        <th>Full Name</th>
                        <td>{user_name}</td>
                    </tr>
                    <tr>
                        <th>Email Address</th>
                        <td>{user_email}</td>
                    </tr>
                    <tr>
                        <th>Phone Number</th>
                        <td>{user_phone}</td>
                    </tr>
                    <tr>
                        <th>Registration Date</th>
                        <td>{date.today().strftime('%B %d, %Y')}</td>
                    </tr>
                    <tr>
                        <th>Registration Time</th>
                        <td>{date.today().strftime('%I:%M %p')}</td>
                    </tr>
                </table>
            </div>

            <div class="action-required">
                <h4>📋 Required Actions</h4>
                <ul>
                    <li>Contact the user within 24 hours</li>
                    <li>Verify user information and requirements</li>
                    <li>Schedule initial consultation call</li>
                    <li>Update CRM with lead information</li>
                </ul>
            </div>

            <div class="footer">
                <p>This notification was generated by the Innovapath registration system.</p>
                <p>Best regards,<br><strong>System Administrator</strong></p>
            </div>
        </div>
    </body>
    </html>
    """

def get_professional_contact_email_content(name: str, email: str, phone: str, message: str) -> str:
    """Professional contact form email in weekly report style"""
    return f"""
<html lang='en'>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f9f9f9;
            color: #333;
            padding: 20px;
            margin: 0;
        }}
        .email-container {{
            max-width: 900px;
            margin: 0 auto;
            background: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: #ffffff;
            text-align: center;
            padding: 25px;
            border-radius: 8px 8px 0 0;
            margin: -30px -30px 30px -30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: bold;
        }}
        .header .subtitle {{
            margin: 5px 0 0 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .lead-priority {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
        }}
        .lead-priority strong {{
            color: #856404;
        }}
        .lead-info {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 25px;
            margin: 20px 0;
        }}
        .lead-info h3 {{
            color: #2c3e50;
            margin-top: 0;
            margin-bottom: 20px;
            font-size: 18px;
        }}
        .info-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        .info-table th {{
            background-color: #a3d9a5;
            color: #000;
            font-weight: bold;
            padding: 12px;
            text-align: left;
            border: 1px solid #ddd;
            width: 30%;
        }}
        .info-table td {{
            padding: 12px;
            border: 1px solid #ddd;
            background-color: #ffffff;
        }}
        .message-section {{
            background-color: #e9ecef;
            border: 1px solid #adb5bd;
            border-radius: 5px;
            padding: 20px;
            margin: 20px 0;
        }}
        .message-section h4 {{
            color: #495057;
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 16px;
        }}
        .message-content {{
            background-color: #ffffff;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            font-style: italic;
            color: #495057;
            line-height: 1.5;
            white-space: pre-wrap;
        }}
        .action-timeline {{
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            border-radius: 5px;
            padding: 20px;
            margin: 20px 0;
        }}
        .action-timeline h4 {{
            color: #0c5460;
            margin-top: 0;
            margin-bottom: 15px;
            text-align: center;
        }}
        .timeline {{
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
        }}
        .timeline-item {{
            flex: 1;
            text-align: center;
            min-width: 120px;
            margin: 5px;
        }}
        .timeline-item .time {{
            font-weight: bold;
            color: #0c5460;
            font-size: 14px;
        }}
        .timeline-item .action {{
            font-size: 12px;
            color: #0c5460;
            margin-top: 5px;
        }}
        .contact-summary {{
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            margin: 15px 0;
            text-align: center;
            border: 1px solid #dee2e6;
        }}
        .contact-summary strong {{
            color: #495057;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #777;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>🚀 Hot Lead Alert</h1>
            <div class="subtitle">New Contact Form Submission</div>
        </div>

        <div class="lead-priority">
            <strong>🔥 HIGH PRIORITY: Contact this lead within 1 hour for best conversion rates!</strong>
        </div>

        <div class="lead-info">
            <h3>👤 Lead Contact Information</h3>
            <table class="info-table">
                <tr>
                    <th>Full Name</th>
                    <td>{name}</td>
                </tr>
                <tr>
                    <th>Email Address</th>
                    <td>{email}</td>
                </tr>
                <tr>
                    <th>Phone Number</th>
                    <td>{phone}</td>
                </tr>
                <tr>
                    <th>Contact Date</th>
                    <td>{date.today().strftime('%B %d, %Y')}</td>
                </tr>
                <tr>
                    <th>Contact Time</th>
                    <td>{date.today().strftime('%I:%M %p')}</td>
                </tr>
            </table>
        </div>

        <div class="message-section">
            <h4>💬 Lead Message</h4>
            <div class="message-content">
                {message}
            </div>
        </div>

        <div class="action-timeline">
            <h4>⏰ Response Timeline</h4>
            <div class="timeline">
                <div class="timeline-item">
                    <div class="time">Within 1 hour</div>
                    <div class="action">Initial contact</div>
                </div>
                <div class="timeline-item">
                    <div class="time">Within 4 hours</div>
                    <div class="action">Qualification call</div>
                </div>
                <div class="timeline-item">
                    <div class="time">Within 24 hours</div>
                    <div class="action">Follow-up email</div>
                </div>
            </div>
        </div>

        <div class="contact-summary">
            <p><strong>📞 Quick Contact:</strong> {phone} | <strong>📧 Email:</strong> {email}</p>
            <p><strong>🎯 Lead Source:</strong> Contact Form | <strong>📊 Priority:</strong> High</p>
        </div>

        <div class="footer">
            <p>This lead was generated through the Innovapath website contact form.</p>
            <p>Best regards,<br><strong>Innovapath Sales Team</strong></p>
        </div>
    </div>
</body>
</html>
"""
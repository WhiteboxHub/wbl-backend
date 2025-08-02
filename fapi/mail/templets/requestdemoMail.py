from datetime import date
from datetime import date

def RequestDemo_User_HTML_template(name: str):
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-color: #f5f8fa;
      color: #333;
      padding: 20px;
      line-height: 1.6;
    }}
    .container {{
      max-width: 700px;
      margin: auto;
      background: #fff;
      padding: 30px;
      border-radius: 12px;
      box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }}
    .header {{
      text-align: center;
      background-color: #0366d6;
      color: white;
      padding: 20px;
      border-radius: 8px 8px 0 0;
    }}
    .footer {{
      margin-top: 30px;
      font-size: 0.9em;
      color: #888;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Thank You, {name}!</h1>
      <h2>Your Demo Request Has Been Received</h2>
    </div>

    <p>We appreciate your interest in <strong>Innovapath</strong>. Your request for a personalized demo has been successfully submitted.</p>

    <p>Our team will contact you soon to schedule the demo and discuss how Innovapath can support your organization with intelligent, AI-driven solutions.</p>

    <p>We look forward to speaking with you!</p>

    <div class="footer">
      — The Innovapath Team<br/>
      <small>Sent on {date.today().strftime('%B %d, %Y')}</small>
    </div>
  </div>
</body>
</html>
"""



def RequestDemo_Admin_HTML_template(name: str, email: str, phone: str, address: str = ""):
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      font-family: Arial, sans-serif;
      background-color: #f5f5f5;
      padding: 20px;
    }}
    .container {{
      background: white;
      padding: 25px;
      border-radius: 10px;
      max-width: 600px;
      margin: auto;
      box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }}
    h2 {{
      color: #0187c8;
      text-align: center;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 20px;
    }}
    td {{
      padding: 10px;
      border-bottom: 1px solid #ccc;
    }}
    .label {{
      font-weight: bold;
      width: 30%;
      background: #f0f0f0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h2>📩  Hello Admin New Demo Request Received</h2>
    <table>
      <tr>
        <td class="label">Name</td>
        <td>{name}</td>
      </tr>
      <tr>
        <td class="label">Email</td>
        <td>{email}</td>
      </tr>
      <tr>
        <td class="label">Phone</td>
        <td>{phone}</td>
      </tr>
      <tr>
        <td class="label">Address</td>
        <td>{address or 'Not Provided'}</td>
      </tr>
      <tr>
        <td class="label">Request Date</td>
        <td>{date.today().strftime('%B %d, %Y')}</td>
      </tr>
    </table>
    <p style="margin-top: 20px;">Please follow up with the user to schedule the demo.</p>
  </div>
</body>
</html>
"""

from datetime import date

def ContactMail_HTML_templete(name, email, phone, message):
    template = f"""
<html lang='en'>
<head>
    <style>
        * {{
            padding: 0px;
            margin: 0px;  
        }}
        body {{
            padding: 0px;
            margin: 0px;
        }}
        .heading {{
            background-color: #0187c8;
            color: #ffffff;
            text-align: center;
            padding: 10px;
        }}
        .contactinfo {{
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }}
        .gridrow {{
            display: grid;
            padding: 10px;
        }}
        table {{
            margin-top: 40px;
        }}
        table, th, td {{
            border: 2px solid black;
            font-size: 20px;
            margin: 40px;
            font-family: Arial, Helvetica, sans-serif;

        }}
        th, td {{
            padding: 8px;
            text-align: center;
        }}
        td {{
            max-width: 250px;
        }}
        .left {{
            font-weight: bolder;
        }}
        footer {{
            width: 100%;
            padding: 10px;
            margin-top: 10px;
            margin-left: 10px;
            font-weight: 600;
            font-size: 16px;
            text-transform: uppercase;
            font-family: "Lucida Console", "Courier New", monospace;
        }}
        span{{
            color:red;
        }}
    </style>
</head>
<body>
    <h1 class='heading'>WBL contact lead generated</h1>
    <div class='contactinfo'>
        <table>
            <tr>
                <td class='left'>NAME</td>
                <td>{name}</td>
            </tr>
            <tr>
                <td class='left'>EMAIL</td>
                <td>{email}</td>
            </tr>
            <tr>
                <td class='left'>PHONE</td>
                <td>{phone}</td>
            </tr>
            <tr>
                <td class='left'>Contact Date</td>
                <td>{date.today()}</td>
            </tr>
            <tr>
                <td class='left'>MESSAGE</td>
                <td>{message}</td>
            </tr>
        </table>
    </div>
    <footer>The above User Requested a contact with the Recruiting team.</footer>
</body>
</html>
"""
    return template

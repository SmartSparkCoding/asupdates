import smtplib
from email.mime.text import MIMEText
from config import EMAIL_FROM, EMAIL_APP_PASSWORD


def send_email(to, subject, html):
    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
        server.send_message(msg)

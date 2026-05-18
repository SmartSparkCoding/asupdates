import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import GMAIL_USER, GMAIL_APP_PASSWORD


def send_email(to_email, subject, html_content):
    """
    Send HTML email via Gmail SMTP.
    
    Args:
        to_email: recipient email address
        subject: email subject
        html_content: HTML content of email
        
    Returns:
        True if successful, False otherwise
    """
    
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[✗] Gmail credentials not configured")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Connect to Gmail SMTP server using TLS
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Upgrade connection to TLS
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        print(f"[✓] Email sent to {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("[✗] Gmail authentication failed - check credentials")
        return False
    except smtplib.SMTPException as e:
        print(f"[✗] SMTP error: {e}")
        return False
    except Exception as e:
        print(f"[✗] Email error: {e}")
        return False


def send_test_email(to_email):
    """Send a test email."""
    html = """
    <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>AS Updates - Test Email</h2>
            <p>This is a test email from AS Updates.</p>
            <p style="color: #666; margin-top: 20px;">
                Sent at: <strong>""" + str(__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + """</strong>
            </p>
        </body>
    </html>
    """
    
    return send_email(to_email, "AS Updates - Test Email", html)

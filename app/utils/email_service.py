import smtplib
from email.mime.text import MIMEText
from app.core.config import get_settings

settings = get_settings()

def send_email_otp(to_email: str, otp: int):
    msg = MIMEText(f"Your AugmintCore verification code is: {otp}")
    msg["Subject"] = "Verify your AugmintCore account"
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, [to_email], msg.as_string())
    except Exception as e:
        print("Error sending email:", e)
        raise

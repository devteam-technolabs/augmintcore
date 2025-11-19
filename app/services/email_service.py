from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings

settings = get_settings()


async def send_verification_email(to_email: str, otp: int):
    msg = EmailMessage()
    msg["Subject"] = "Your Email Verification Code"
    msg["From"] = settings.SMTP_USER  # MUST match Gmail login
    msg["To"] = to_email
    msg.set_content(f"Your verification code is: {otp}")

    try:
        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,  # Must be Gmail App Password
        )

        print("Email sent successfully!")
        return True

    except Exception as e:
        print("Email sending error:", e)
        return False

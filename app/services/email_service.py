from email.message import EmailMessage

import aiosmtplib
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


async def send_verification_email(
    to_email: str, otp: int, full_name: str, title: str = "Your OTP for Augmint"
):
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email
    print(otp)

    # Extract first name from full name
    # Render template
    html = templates.get_template("send_otp_email_template.html").render(
        full_name=full_name,
        otp=otp,
        email_bg_url="https://reone-bucket-new.s3.ca-central-1.amazonaws.com/emailBg.png",
        logo_url="https://reone-bucket-new.s3.ca-central-1.amazonaws.com/logo.png",
    )

    msg.set_content("Your email client does not support HTML.")
    msg.add_alternative(html, subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
        )
        print("OTP email sent successfully!")
        return True

    except Exception as e:
        print("Email sending error:", e)
        return False

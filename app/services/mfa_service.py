import pyotp
import qrcode
import io
import base64
from io import BytesIO

def generate_mfa_secret():
    return pyotp.random_base32()


def verify_mfa_token(secret: str, token: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(token)


def generate_totp_uri(email: str, secret: str):
    issuer = "AugmintCore"
    return pyotp.totp.TOTP(secret).provisioning_uri(email, issuer_name=issuer)

def generate_qr_code(uri: str):
   

    qr = qrcode.make(uri)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")

    return base64.b64encode(buffered.getvalue()).decode()


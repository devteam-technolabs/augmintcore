import base64
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from app.core.config import get_settings    
settings = get_settings()

KMS_KEY_ID = settings.KMS_KEY_ID

kms = boto3.client("kms", aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                   aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                   region_name=settings.AWS_REGION)

async def encrypt_value(value: str) -> str:
    try:
        encrypted = kms.encrypt(
            KeyId=KMS_KEY_ID,
            Plaintext=value.encode("utf-8")
        )
        return base64.b64encode(encrypted["CiphertextBlob"]).decode()
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Encryption failed: {e}")


async def decrypt_value(encrypted: str) -> str:
    try:
        decoded = base64.b64decode(encrypted)
        decrypted = kms.decrypt(
            CiphertextBlob=decoded
        )
        return decrypted["Plaintext"].decode()
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Decryption failed: {e}")

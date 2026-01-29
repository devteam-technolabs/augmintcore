import base64

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings

settings = get_settings()


class KMSService:
    def __init__(self):
        self.client = boto3.client(
            "kms",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.key_id = settings.KMS_KEY_ID

    # async def encrypt(self, value: str) -> str:
    #     try:
    #         encrypted = self.client.encrypt(
    #             KeyId=self.key_id,
    #             Plaintext=value.encode("utf-8")
    #         )
    #         return base64.b64encode(encrypted["CiphertextBlob"]).decode()
    #     except (BotoCoreError, ClientError) as e:
    #         raise RuntimeError(f"KMS encryption failed: {e}")

    async def encrypt(self, value: str | None) -> str | None:
        if not value:
            return None  # 👈 VERY IMPORTANT

        try:
            encrypted = self.client.encrypt(
                KeyId=self.key_id, Plaintext=value.encode("utf-8")
            )
            return base64.b64encode(encrypted["CiphertextBlob"]).decode()
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"KMS encryption failed: {e}")

    async def decrypt(self, encrypted_value: str) -> str:
        try:
            decoded = base64.b64decode(encrypted_value)
            decrypted = self.client.decrypt(CiphertextBlob=decoded)
            return decrypted["Plaintext"].decode()
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"KMS decryption failed: {e}")


# Singleton instance
kms_service = KMSService()

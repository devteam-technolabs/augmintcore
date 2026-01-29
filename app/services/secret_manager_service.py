import json

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings

settings = get_settings()


class SecretsManagerService:
    def __init__(self):
        self.client = boto3.client(
            "secretsmanager",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.secret_prefix = "trading-user"

    def _get_secret_name(self, user_id: int, exchange_name: str) -> str:
        """Generate consistent secret name for user exchange"""
        return f"{self.secret_prefix}/{exchange_name}/{user_id}"

    async def store_exchange_credentials(
        self,
        user_id: int,
        exchange_name: str,
        api_key: str,
        api_secret: str,
        passphrase: str | None = None,
    ) -> str:
        """
        Store exchange API credentials in AWS Secrets Manager
        Returns the ARN of the created/updated secret
        """
        secret_name = self._get_secret_name(user_id, exchange_name)

        # Prepare secret value
        secret_value = {
            "api_key": api_key,
            "api_secret": api_secret,
        }

        if passphrase:
            secret_value["passphrase"] = passphrase

        try:
            # Try to update existing secret
            response = self.client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(secret_value),
                Description=f"API credentials for {exchange_name} exchange - User {user_id}",
            )
            return response["ARN"]

        except self.client.exceptions.ResourceNotFoundException:
            # Secret doesn't exist, create new one
            response = self.client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_value),
                Description=f"API credentials for {exchange_name} exchange - User {user_id}",
                Tags=[
                    {"Key": "user_id", "Value": str(user_id)},
                    {"Key": "exchange", "Value": exchange_name},
                    {"Key": "service", "Value": "trading-bot"},
                ],
            )
            return response["ARN"]

        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Secrets Manager store failed: {e}")

    async def retrieve_exchange_credentials(
        self, user_id: int, exchange_name: str
    ) -> dict:
        """
        Retrieve exchange API credentials from AWS Secrets Manager
        Returns dict with api_key, api_secret, and passphrase (if exists)
        """
        secret_name = self._get_secret_name(user_id, exchange_name)

        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response["SecretString"])
            return secret_data

        except self.client.exceptions.ResourceNotFoundException:
            raise ValueError(
                f"Credentials not found for user {user_id} on {exchange_name}"
            )

        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Secrets Manager retrieval failed: {e}")

    async def delete_exchange_credentials(
        self, user_id: int, exchange_name: str, force: bool = False
    ) -> bool:
        """
        Delete exchange API credentials from AWS Secrets Manager
        If force=False, schedules deletion in 7 days (default AWS behavior)
        If force=True, deletes immediately without recovery window
        """
        secret_name = self._get_secret_name(user_id, exchange_name)

        try:
            if force:
                self.client.delete_secret(
                    SecretId=secret_name,
                    ForceDeleteWithoutRecovery=True,
                )
            else:
                self.client.delete_secret(
                    SecretId=secret_name,
                    RecoveryWindowInDays=7,
                )
            return True

        except self.client.exceptions.ResourceNotFoundException:
            return False

        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Secrets Manager deletion failed: {e}")

    async def secret_exists(self, user_id: int, exchange_name: str) -> bool:
        """Check if secret exists for given user and exchange"""
        secret_name = self._get_secret_name(user_id, exchange_name)

        try:
            self.client.describe_secret(SecretId=secret_name)
            return True
        except self.client.exceptions.ResourceNotFoundException:
            return False
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Secrets Manager check failed: {e}")


# Singleton instance
secrets_manager_service = SecretsManagerService()

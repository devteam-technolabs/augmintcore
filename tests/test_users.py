import boto3
from botocore.exceptions import ClientError

# def check_secret_exists(user_id: int, exchange_name: str):
#     secret_name = f"trading-user/{exchange_name}/{user_id}"

#     client = boto3.client(
#         "secretsmanager",
#         aws_access_key_id=AWS_ACCESS_KEY_ID,
#         aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
#         region_name=AWS_REGION,
#     )

#     try:
#         client.describe_secret(SecretId=secret_name)
#         print(f"✅ Secret EXISTS: {secret_name}")
#         return True

#     except client.exceptions.ResourceNotFoundException:
#         print(f"❌ Secret NOT FOUND: {secret_name}")
#         return False

#     except ClientError as e:
#         print(f"⚠️ AWS Error: {e}")
#         return False


# # Example usage
# check_secret_exists(user_id=101, exchange_name="binance")


def list_all_trading_secrets():
    client = boto3.client(
        "secretsmanager",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )

    response = client.list_secrets()

    print("✅ Secrets Stored in AWS:\n")

    for secret in response["SecretList"]:
        if secret["Name"].startswith("trading-user/"):
            print("➡️", secret["Name"])


list_all_trading_secrets()

import asyncio
from app.security.kms_service import kms_service

async def main():
    print("API KEY ENC:")
    print(
        await kms_service.encrypt(
            "76d97f29a7dba9afae61da53abdc172e"
        )
    )

    print("\nSECRET ENC:")
    print(
        await kms_service.encrypt(
            "h3xlRF1bpXKrZM6I03Q4hTn1vw7por2rUM7vL+MK75PW9l3AnY6u/bJZvW30vOCeo81PvN+Mm/RhGjPcpXrJIQ=="
        )
    )

    print("\nPASSPHRASE ENC:")
    print(
        await kms_service.encrypt(
            "5gzc1ji04g2v"
        )
    )

if __name__ == "__main__":
    asyncio.run(main())

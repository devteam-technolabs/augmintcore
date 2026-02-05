import os

from fastapi import HTTPException, UploadFile
from sqlalchemy.future import select

from app.models.user import Address, User
from app.utils.settings_utils import get_absolute_media_url


async def get_user_profile(user: User, request):
    return {
        "profile_image": get_absolute_media_url(request, user.profile_image),
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
    }


async def update_user_profile(db, user: User, data, image: UploadFile, request):

    # Unique Email Validation
    if data.email and data.email != user.email:
        existing = await db.execute(select(User).where(User.email == data.email))
        if existing.scalar():
            raise HTTPException(400, "Email already exists")

        user.email = data.email

    # Unique Phone Validation
    if data.phone_number and data.phone_number != user.phone_number:
        existing = await db.execute(
            select(User).where(User.phone_number == data.phone_number)
        )
        if existing.scalar():
            raise HTTPException(400, "Phone number already exists")

        user.phone_number = data.phone_number

    # Update Full Name
    if data.full_name:
        user.full_name = data.full_name

    # Handle Image Upload
    if image:
        filename = f"user_{user.id}_{image.filename}"
        upload_path = f"media/profile_images/{filename}"

        os.makedirs("media/profile_images", exist_ok=True)

        with open(upload_path, "wb") as f:
            f.write(await image.read())

        user.profile_image = upload_path.replace("media/", "media/")

    await db.commit()
    await db.refresh(user)

    return await get_user_profile(user, request)


async def get_user_address(db, user_id: int):
    result = await db.execute(select(Address).where(Address.user_id == user_id))
    return result.scalar()


async def update_user_address(db, address, data):

    for field, value in data.dict(exclude_unset=True).items():
        setattr(address, field, value)

    await db.commit()
    await db.refresh(address)
    return address

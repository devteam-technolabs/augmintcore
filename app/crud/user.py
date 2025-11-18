from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import User, Address
from app.utils.hashing import hash_password
from fastapi import Depends, HTTPException
from datetime import datetime, timedelta
import random
from fastapi.security import OAuth2PasswordBearer
from app.core.config import get_settings
from app.db.session import get_async_session
from jose import JWTError, jwt

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


class CRUDUser:

    async def get_by_email(self, db: AsyncSession, email: str):
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def create(self, db, obj_in):
        otp = random.randint(100000, 999999)

        db_obj = User(
            email=obj_in.email,
            hashed_password=hash_password(obj_in.password),
            email_otp=otp,
            email_otp_expiry=datetime.utcnow() + timedelta(minutes=5),
            full_name=obj_in.full_name,
            phone_number=obj_in.phone_number,
            country_code=obj_in.country_code,
        )

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    

    async def resend_otp(self, db, email: str):
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.is_email_verify:
            raise HTTPException(status_code=400, detail="Email already verified")

        user.email_otp = random.randint(100000, 999999)
        user.email_otp_expiry = datetime.utcnow() + timedelta(minutes=5)

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user
    

    async def verify_email(self, db, email: str, otp: int):
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.is_email_verify:
            raise HTTPException(status_code=400, detail="Email already verified")

        if user.email_otp_expiry < datetime.utcnow():
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

        if user.email_otp != otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        # Mark verified
        user.is_email_verify = True
        user.email_otp = None
        user.email_otp_expiry = None

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user
    
    async def create_address(self, db, obj_in, user_id: int):
        db_obj = Address(
            user_id=user_id,
            street_address=obj_in.street_address,
            city=obj_in.city,
            state=obj_in.state,
            zip_code=obj_in.zip_code,
            country=obj_in.country
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_session)) -> User:
        credentials_exception = HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, settings.ACCESS_SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get('user_id')
            if user_id is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        
        user = await db.get(User, int(user_id))
        if not user:
            raise credentials_exception
        return user


crud_user = CRUDUser()

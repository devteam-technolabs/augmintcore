import random
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException

# from fastapi.security import OAuth2PasswordBearer
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import get_settings
from app.db.session import get_async_session
from app.models.user import Address, User
from app.utils.hashing import hash_password
from app.services.payment_service import payment_service
settings = get_settings()

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")
bearer_scheme = HTTPBearer()


class AuthUser:

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
            raise HTTPException(
                status_code=400, detail="OTP has expired. Please request a new one."
            )

        if user.email_otp != otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        # Mark verified
        user.is_email_verify = True
        if user.is_email_verify ==True:
            user.step=1
        stripe_id = await payment_service.create_stripe_customer_id(user)
        user.stripe_customer_id = stripe_id
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
            country=obj_in.country,
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        db: AsyncSession = Depends(get_async_session),
    ) -> User:
        token = credentials.credentials
        # credentials_exception = HTTPException(
        #     status_code=401,
        #     detail="Could not validate credentials",
        #     headers={"WWW-Authenticate": "Bearer"},
        # )
        try:
            payload = jwt.decode(
                token, settings.ACCESS_SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid Token")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user = await db.get(User, int(user_id))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user


auth_user = AuthUser()




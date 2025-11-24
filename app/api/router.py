from datetime import timedelta
import random
from datetime import datetime, timedelta
from passlib.context import CryptContext
import re
import pyotp
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import get_settings
from app.crud.user import crud_user
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.user import (
    AddressCreate,
    LoginResponse,
    MessageUserResponse,
    MFAEnableResponse,
    MFAResetResponse,
    MFAVerifyResponse,
    UserCreate,
    UserResponse,
    UserWithAddressResponse,
    VerifyOtpRequest,
    ForgotPasswordRequest,VerifyResetOTPRequest,
    ResetPasswordRequest
)
from app.services.auth_service import create_access_token, create_refresh_token,verify_passwword
from app.services.email_service import send_verification_email
from app.services.mfa_service import (
    generate_mfa_secret,
    generate_qr_code,
    generate_totp_uri,
)
from app.utils.hashing import hash_password

settings = get_settings()
from jose import jwt

router = APIRouter(prefix="/users", tags=["Users"])


# -------------------------------
# SIGNUP
# -------------------------------
@router.post("/signup", response_model=MessageUserResponse)
async def signup(
    data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    user = await crud_user.get_by_email(db, data.email)
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = await crud_user.create(db, data)

    first_name = new_user.full_name.split(" ")[0] if new_user.full_name else "User"

    background_tasks.add_task(
        send_verification_email,
        new_user.email,
        new_user.email_otp,
        first_name,
        title="Your OTP for Augmint"
    )

    return {
        "message": "User created successfully. Please check your email to verify your account.",
        "user": new_user,
    }


# -------------------------------
# RESEND OTP
# -------------------------------
@router.post("/resend-otp", response_model=MessageUserResponse)
async def resend_otp(
    email: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    user = await crud_user.resend_otp(db, email)

    first_name = user.full_name.split(" ")[0] if user.full_name else "User"
  
    

    background_tasks.add_task(send_verification_email, user.email, user.email_otp, first_name,
        title="Your Resend OTP for Augmint")

    return {"message": "A new OTP has been sent to your email.", "user": user}


# -------------------------------
# VERIFY OTP
# -------------------------------
@router.post("/verify-otp", response_model=MessageUserResponse)
async def verify_otp(
    data: VerifyOtpRequest, db: AsyncSession = Depends(get_async_session)
):
    user = await crud_user.verify_email(db, data.email, data.otp)

    access = create_access_token({"user_id": user.id})
    refresh = create_refresh_token({"user_id": user.id})

    return {
        "message": "Email verified successfully!",
        "user": user,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/create-address", response_model=UserWithAddressResponse)
async def create_address(
    data: AddressCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user=Security(crud_user.get_current_user),
):
    user = current_user

    # 2. Create new address
    address = await crud_user.create_address(db, data, user.id)

    # 3. Attach to user
    user.address = address

    return {"message": "Address created successfully", "user": user}


@router.post("/enable-mfa", response_model=MFAEnableResponse)
async def enable_mfa(
    db: AsyncSession = Depends(get_async_session),
    current_user=Security(crud_user.get_current_user),
):
    user = current_user
    user_id = user.id
    # Query user (ASYNC)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate secret
    secret = generate_mfa_secret()
    user.mfa_secret = secret
    user.is_mfa_enabled = False

    # Save to DB
    await db.commit()
    await db.refresh(user)

    # Create QR URI and QR image
    uri = generate_totp_uri(user.email, secret)
    qr_code = generate_qr_code(uri)

    return {
        "message": "MFA enabled",
        "secret": secret,
        "qr_code_base64": f"data:image/png;base64,{qr_code}",
        "user": user,
    }


@router.post("/verify-mfa", response_model=MFAVerifyResponse)
async def verify_mfa(
    otp: str,
    db: AsyncSession = Depends(get_async_session),
    current_user=Security(crud_user.get_current_user),
):
    user = current_user
    user_id = user.id
    # Fetch user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not enabled for this user")

    # Already verified?
    if user.is_mfa_enabled:
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        return {
            "message": "MFA already verified",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,
        }

    totp = pyotp.TOTP(user.mfa_secret)

    # Validate OTP
    if not totp.verify(otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Mark MFA as verified
    user.is_mfa_enabled = True
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token = create_access_token(
        {"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = create_refresh_token({"sub": str(user.id)})

    return {
        "message": "MFA verified successfully",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/disable-mfa", response_model=MFAVerifyResponse)
async def disable_mfa(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user=Security(crud_user.get_current_user),
):
    user = current_user
    user_id = user.id
    # Fetch user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not enabled")

    # Disable MFA
    user.mfa_secret = None
    user.is_mfa_enabled = False
    user.is_mfa_verified = False

    await db.commit()
    await db.refresh(user)

    return {"message": "MFA disabled successfully", "user": user}


@router.post("/reset-mfa", response_model=MFAResetResponse)
async def reset_mfa(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user=Security(crud_user.get_current_user),
):
    user = current_user
    user_id = user.id
    # Fetch user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate new secret
    new_secret = pyotp.random_base32()

    user.mfa_secret = new_secret
    user.is_mfa_enabled = True
    user.is_mfa_verified = False  # Must verify again

    await db.commit()
    await db.refresh(user)

    # Generate QR URI
    uri = f"otpauth://totp/{user.email}?secret={new_secret}&issuer=YourApp"
    qr_code = generate_qr_code(uri)

    return {
        "message": "MFA reset successful. Scan the new QR code.",
        "new_secret": new_secret,
        "qr_code_base64": f"data:image/png;base64,{qr_code}",
        "user": user,
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    email: str, password: str, db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Invalid credentials")

    if not user.verify_password(password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # CASE 1: MFA Enabled → Do NOT issue tokens yet
    # if user.is_mfa_enabled:
    #     return LoginResponse(
    #         message="MFA required",
    #         mfa_required=True,
    #         user=UserResponse.model_validate(user)
    #     )

    # CASE 2: MFA NOT enabled → Issue tokens now
    access = create_access_token({"user_id": user.id})
    refresh = create_refresh_token({"user_id": user.id})

    return LoginResponse(
        message="Login successful",
        mfa_required=False,
        user=UserResponse.model_validate(user),
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
    )


@router.post("/refresh-token")
async def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(
            refresh_token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("user_id")

        new_access = create_access_token({"user_id": user_id})
        return {"access_token": new_access, "token_type": "bearer"}

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/forgot-password",response_model= MessageUserResponse)
async def forgot_password(data: ForgotPasswordRequest,background_tasks:BackgroundTasks
, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = random.randint(100000, 999999)
    user.email_otp = otp
    user.email_otp_expiry = datetime.utcnow() + timedelta(minutes=5)
    db.add(user)

    await db.commit()
    await db.refresh(user)
    first_name = user.full_name.split(" ")[0] if user.full_name else "User"
    background_tasks.add_task(send_verification_email, user.email, user.email_otp, first_name,
        title="Your Reset OTP for Augmint")

    # TODO: send otp via email or sms
    print("Reset OTP:", otp)

    return {"message": "Reset OTP sent to registered email","user":user}


@router.post("/forgot_password_verify",response_model= MessageUserResponse)
async def forgot_password_verify(data:VerifyOtpRequest,db:AsyncSession =Depends(get_async_session)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_otp != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.email_otp_expiry < user.email_otp_expiry:
        raise HTTPException(status_code=400, detail="OTP expired")

    user.email_otp = None
    user.email_otp_expiry = None
    db.add(user)

    await db.commit()
    await db.refresh(user)

    return {"message": "OTP verified successfully","user":user}
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
@router.post("/reset_password",response_model= MessageUserResponse)
async def reset_password(data:ResetPasswordRequest,db:AsyncSession =Depends(get_async_session)):
    results = await db.execute(select(User).where(User.email==data.email))
    user = results.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if pwd_context.verify(data.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="New password must be different from old password")
    
    if data.new_password!=data.confirm_password:
        raise HTTPException(status_code=400,detail="Passwords do not match.")
    
    try:
        verify_passwword(data.confirm_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    user.password= hash_password(data.new_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"message": "Password reset successfully","user":user}

    
    



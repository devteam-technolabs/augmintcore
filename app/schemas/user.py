import re
from datetime import datetime
from typing import Optional
from typing import List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, validator
from typing import Literal

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    # phone_number: Optional[str] = None
    phone_number: str = Field(..., description="Phone number must be unique across all users. Format: +[country_code][number], e.g., +1-123-456-7890")
    country_code: Optional[str] = None

    @validator("password")
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:'\",.<>/?]", v):
            raise ValueError("Password must contain at least one special character")
        return v

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v

    @validator("phone_number")
    def validate_phone_number(cls, v):
        # Basic format validation (adjust regex as needed for your requirements, e.g., international format)
        if not re.match(r'^\+?\d{1,4}[-.\s]?\d{1,14}$', v):
            raise ValueError("Invalid phone number format. Use international format like +1-123-456-7890")
        # Note: Uniqueness must be enforced in the service/endpoint layer by querying the database
        # (e.g., check if a user with this phone_number already exists before creating the user).
        # Example: if User.query.filter_by(phone_number=v).first(): raise ValueError("Phone number already in use")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None = None
    phone_number: str | None = None
    country_code: str | None = None
    is_active: bool
    is_email_verify: bool
    is_mfa_enabled: bool
    is_phone_verify: bool
    is_exchange_connected: bool | None = False
    role: str
    created_at: datetime
    updated_at: datetime
    step: Optional[int] = 0
    addresses: List["AddressResponse"] = Field(default_factory=list)
    class Config:
        from_attributes = True
    


class MessageUserResponse(BaseModel):
    message: str
    user: UserResponse
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    status_code: Optional[int] = None


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: int
    model_config = ConfigDict(from_attributes=True)


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: int
    model_config = ConfigDict(from_attributes=True)


# --------------------
# ADDRESS CREATE
# --------------------
class AddressCreate(BaseModel):
    street_address: str
    city: str
    state: Optional[str] = None
    zip_code: str
    country: str
    step : Optional[int] = 0


class AddressResponse(BaseModel):
    id: int
    user_id: int
    street_address: str
    city: str
    state: str | None = None
    zip_code: str
    country: str

    class Config:
        from_attributes = True


# --------------------
# FINAL RETURN FOR CREATE ADDRESS
# --------------------
class UserWithAddressResponse(BaseModel):
    message: str
    user: UserResponse

    class Config:
        from_attributes = True


class MFAResetResponse(BaseModel):
    message: str
    new_secret: str
    qr_code_base64: str
    user: UserResponse
    model_config = ConfigDict(from_attributes=True)
    status_code :Optional[int] = None


class MFAEnableResponse(BaseModel):
    message: str
    secret: str
    qr_code_base64: str
    user: UserResponse
    model_config = ConfigDict(from_attributes=True)
    status_code :Optional[int] = None


class MFAVerifyResponse(BaseModel):
    message: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = "bearer"
    user: UserResponse
    status_code :Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    message: str
    mfa_required: bool
    user: Optional[UserResponse] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    status_code :Optional[int] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str
    confirm_password: str

    # @validator("new_password")
    # def validate_password_strength(cls, v):
    #     if len(v) < 8:
    #         raise ValueError("Password must be at least 8 characters long")
    #     if not re.search(r"[A-Z]", v):
    #         raise ValueError("Password must contain at least one uppercase letter")
    #     if not re.search(r"[a-z]", v):
    #         raise ValueError("Password must contain at least one lowercase letter")
    #     if not re.search(r"\d", v):
    #         raise ValueError("Password must contain at least one digit")
    #     if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:'\",.<>/?]", v):
    #         raise ValueError("Password must contain at least one special character")
    #     return v

    # @validator("confirm_password")
    # def passwords_match(cls, v, values):
    #     if "new_password" in values and v != values["new_password"]:
    #         raise ValueError("Passwords do not match")
    #     return v

class MFAVerifyRequest(BaseModel):
    otp: str

class CheckoutSessionSchemas(BaseModel):
    plan_duration: Literal['monthly','yearly']
    plan_name:str

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    status_code :Optional[int] = None

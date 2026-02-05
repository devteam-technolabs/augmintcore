from typing import Optional

from pydantic import BaseModel


class UserDetailResponse(BaseModel):
    profile_image: Optional[str]
    full_name: Optional[str]
    email: str
    phone_number: Optional[str]
    country_code: Optional[str]


class UserUpdateRequest(BaseModel):
    full_name: Optional[str]
    email: Optional[str]
    phone_number: Optional[str]


class AddressResponse(BaseModel):
    street_address: str
    city: str
    state: Optional[str]
    zip_code: str
    country: str


class AddressUpdateRequest(BaseModel):
    street_address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    country: Optional[str]

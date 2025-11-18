from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
# Import Base from your shared base file, not from declarative_base()
from app.db.base import Base

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    country_code = Column(String(10), nullable=True)
    email_otp = Column(Integer, nullable=True)
    email_otp_expiry = Column(DateTime, nullable=True)
    phone_otp = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=False)
    is_email_verify = Column(Boolean, default=False)
    mfa_secret = Column(String, nullable=True)
    is_mfa_enabled = Column(Boolean, default=False)
    is_phone_verify = Column(Boolean, default=False)
    role = Column(String(50), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.hashed_password = pwd_context.hash(password)   # <-- FIXED

    def verify_password(self, password: str):
        return pwd_context.verify(password, self.hashed_password)  # <-- FIXED

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
    

class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    street_address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=False)
    country = Column(String, nullable=False)

    user = relationship("User", back_populates="addresses")


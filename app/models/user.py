from datetime import datetime
from email.policy import default
import enum
from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String,Enum as SAEnum
from sqlalchemy.orm import relationship

# Import Base from your shared base file, not from declarative_base()
from app.db.base import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
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
    is_address_filled = Column(Boolean, default=False)
    is_payment_done = Column(Boolean, default=False)
    is_exchange_connected = Column(Boolean, default=False,nullable=True)
    role = Column(String(50), default="user")
    step = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    addresses = relationship(
        "Address", back_populates="user", cascade="all, delete-orphan",lazy="selectin"
    )
    subscriptions = relationship(
        "Subscription",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    transactions = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    exchange_accounts = relationship(
        "UserExchange", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )



    def set_password(self, password: str):
        self.hashed_password = pwd_context.hash(password)  # <-- FIXED

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

class SubscriptionStatus(enum.Enum):
    active = "active"
    canceled = "canceled"
    past_due = "past_due"
    incomplete = "incomplete"
    trialing = "trialing"

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer,primary_key=True,index=True)
    user_id = Column(Integer,ForeignKey("users.id",ondelete="CASCADE"))
    plan_name = Column(String(50), nullable=False)
    plan_type = Column(String(50), nullable=False)
    price = Column(Integer, nullable=False)
    stripe_subscription_id = Column(String(255), nullable=True)
    status = Column(SAEnum(SubscriptionStatus,name="subscription_status"),
    nullable=True,
    )  # active, canceled, past_due, etc.
    cancel_at_period_end = Column(Boolean, nullable=True,default=False)
    final_cancellation_date = Column(DateTime, nullable=True)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # relationships
    user = relationship("User", back_populates="subscriptions")
    transactions = relationship(
        "Transaction",
        back_populates="subscription",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"))

    amount = Column(Integer, nullable=False)  # amount in cents
    currency = Column(String(10), default="usd")
    stripe_event_id = Column(String(255), unique=True, nullable=False)
    type = Column(String(50), nullable=False)  # invoice.paid, refund, etc.

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
    subscription = relationship("Subscription", back_populates="transactions")


class UserExchange(Base):
    __tablename__ = "user_exchanges"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    exchange_name = Column(String(50), nullable=False)  # "coinbase"
    api_key = Column(String(255), nullable=False)
    api_secret = Column(String(255), nullable=False)
    passphrase = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="exchange_accounts")
from sqlalchemy import Column, Integer, String, DateTime
from .database import Base
from sqlalchemy import Column, DateTime, func
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    key_office = Column(String, nullable=False)  # Thêm thuộc tính mới
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GmailLog(Base):
    __tablename__ = "gmail_log"
    id = Column(Integer, primary_key=True, index=True)
    gmail = Column(String, nullable=False)
    otp = Column(String, nullable=False)
    otp_expiry = Column(DateTime, nullable=False)

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    # gmail = Column(String, unique=True, index=True)

class GmailLog(Base):
    __tablename__ = "gmail_log"
    id = Column(Integer, primary_key=True, index=True)
    gmail = Column(String, index=True)
    otp_code = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    expired_at = Column(DateTime)  # thời gian hết hạn OTP

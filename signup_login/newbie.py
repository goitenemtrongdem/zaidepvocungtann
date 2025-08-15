from fastapi import FastAPI, HTTPException, Depends, Form
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import random
import smtplib
from email.mime.text import MIMEText

# ====== CẤU HÌNH DATABASE ======
DATABASE_URL = "postgresql://postgres:280800leuleu@localhost/mydb"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

# ====== MÃ HÓA PASSWORD ======
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ====== MODEL ======
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)

class GmailLog(Base):
    __tablename__ = "gmail_log"
    id = Column(Integer, primary_key=True, index=True)
    gmail = Column(String, nullable=False)
    otp = Column(String, nullable=False)
    otp_expiry = Column(DateTime, nullable=False)

Base.metadata.create_all(bind=engine)

# ====== FASTAPI APP ======
app = FastAPI()

# ====== DEPENDENCY ======
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ====== HÀM GỬI EMAIL ======
def send_email(to_email, otp_code):
    sender_email = "huyozil1234@gmail.com"
    sender_password = "qobsxxoijobnqhrl"

    msg = MIMEText(f"Your OTP code is: {otp_code}. It will expire in 60 seconds.")
    msg["Subject"] = "Your OTP Code"
    msg["From"] = sender_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)

# ====== 1. ĐĂNG KÝ ======
@app.post("/register")
def register(
    username: str = Form(...),
    email: EmailStr = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(password)
    new_user = User(username=username, email=email, phone=phone, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()

    return {"message": "User registered successfully"}

# ====== 2. ĐĂNG NHẬP ======
@app.post("/login")
def login(
    gmail: EmailStr = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == gmail).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    otp_code = str(random.randint(1000, 9999))
    expiry_time = datetime.utcnow() + timedelta(seconds=60)

    gmail_log = GmailLog(gmail=gmail, otp=otp_code, otp_expiry=expiry_time)
    db.add(gmail_log)
    db.commit()

    send_email(gmail, otp_code)

    return {"message": "OTP sent to your email"}

# ====== 3. XÁC MINH OTP ======
from fastapi.responses import JSONResponse

# ====== 3. XÁC MINH OTP (BỎ NHẬP GMAIL) ======
@app.post("/verify-otp")
def verify_otp(
    otp: str = Form(...),
    db: Session = Depends(get_db)
):
    # Lấy gmail của lần gửi OTP gần nhất
    log_entry = db.query(GmailLog).order_by(GmailLog.id.desc()).first()

    if not log_entry:
        raise HTTPException(status_code=400, detail="No OTP found")

    if datetime.utcnow() > log_entry.otp_expiry:
        # Nếu hết hạn → gửi thông báo và nút resend
        return JSONResponse(
            status_code=400,
            content={
                "detail": "OTP expired",
                "resend_endpoint": "/resend-otp"
            }
        )

    if log_entry.otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    return {"message": "Login successful"}


# ====== 4. RESEND OTP ======
@app.post("/resend-otp")
def resend_otp(db: Session = Depends(get_db)):
    # Lấy gmail của lần login gần nhất
    last_entry = db.query(GmailLog).order_by(GmailLog.id.desc()).first()
    if not last_entry:
        raise HTTPException(status_code=400, detail="No previous login found")

    gmail = last_entry.gmail

    # Xóa tất cả OTP cũ
    db.query(GmailLog).delete()
    db.commit()

    # Tạo OTP mới
    otp_code = str(random.randint(1000, 9999))
    expiry_time = datetime.utcnow() + timedelta(seconds=60)

    new_log = GmailLog(gmail=gmail, otp=otp_code, otp_expiry=expiry_time)
    db.add(new_log)
    db.commit()

    send_email(gmail, otp_code)

    return {"message": f"New OTP sent to {gmail}"}

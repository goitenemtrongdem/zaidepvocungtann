from fastapi import APIRouter, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
from datetime import datetime, timedelta, timezone
from .database import get_db
from .models import User, GmailLog
from .utils import hash_password, verify_password, send_email

router = APIRouter()

# ===== Đăng ký =====
import re
from fastapi import HTTPException

def is_valid_password(password: str) -> bool:
    # Regex kiểm tra độ mạnh của mật khẩu
    pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{9,}$"
    return bool(re.match(pattern, password))
@router.post("/register")
def register(
    username: str = Form(...),
    email: EmailStr = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    key_office: str = Form(...),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    if not is_valid_password(password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 9 characters long, contain uppercase, lowercase, number, and special character"
        )

    # Tìm key_office
    key_office_row = db.query(User).filter(User.key_office == key_office).first()
    if key_office_row:
        # Kiểm tra hạn 1 tuần
        if datetime.now(timezone.utc) - key_office_row.created_at > timedelta(weeks=1):
            db.delete(key_office_row)  # Quá hạn thì xóa
            db.commit()
        else:
            # Chưa quá hạn thì xóa dữ liệu cũ để thay thế
            db.query(User).filter(User.key_office == key_office).delete()
            db.commit()

    # Thêm user mới
    new_user = User(
        username=username,
        email=email,
        phone=phone,
        hashed_password=hash_password(password),
        key_office=key_office,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()

    return {"message": f"User registered successfully for key_office {key_office}"}





# ===== Đăng nhập =====
@router.post("/login")
def login(
    gmail: EmailStr = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Tìm user bằng gmail
    user = db.query(User).filter(User.email == gmail).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Tạo mã OTP
    otp_code = str(random.randint(1000, 9999))
    expiry_time = datetime.utcnow() + timedelta(seconds=60)

    # Xóa OTP cũ của user
    db.query(GmailLog).filter(GmailLog.gmail == gmail).delete()
    db.commit()

    # Lưu OTP mới
    gmail_log = GmailLog(gmail=gmail, otp=otp_code, otp_expiry=expiry_time)
    db.add(gmail_log)
    db.commit()

    # Gửi OTP qua email
    send_email(gmail, otp_code)

    return {"message": f"OTP sent to {gmail}, valid for 60 seconds"}


# ===== Xác minh OTP =====
@router.post("/verify-otp")
def verify_otp(
    otp: str = Form(...),
    db: Session = Depends(get_db)
):
    # Lấy OTP gần nhất
    log_entry = db.query(GmailLog).order_by(GmailLog.id.desc()).first()

    if not log_entry:
        raise HTTPException(status_code=400, detail="No OTP found")

    # Kiểm tra hết hạn
    if datetime.utcnow() > log_entry.otp_expiry:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "OTP expired",
                "resend_endpoint": "/resend-otp"
            }
        )

    # Kiểm tra sai OTP
    if log_entry.otp != otp:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Invalid OTP",
                "resend_endpoint": "/resend-otp"
            }
        )

    return {"message": "Login successful"}


# ===== Gửi lại OTP =====
@router.post("/resend-otp")
def resend_otp(db: Session = Depends(get_db)):
    # Lấy gmail gần nhất
    last_entry = db.query(GmailLog).order_by(GmailLog.id.desc()).first()
    if not last_entry:
        raise HTTPException(status_code=400, detail="No previous login found")

    gmail = last_entry.gmail

    # Xóa tất cả OTP cũ
    db.query(GmailLog).filter(GmailLog.gmail == gmail).delete()
    db.commit()

    # Tạo OTP mới
    otp_code = str(random.randint(1000, 9999))
    expiry_time = datetime.utcnow() + timedelta(seconds=60)

    new_log = GmailLog(gmail=gmail, otp=otp_code, otp_expiry=expiry_time)
    db.add(new_log)
    db.commit()

    send_email(gmail, otp_code)

    return {"message": f"New OTP sent to {gmail}"}


# from apscheduler.schedulers.background import BackgroundScheduler

# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# def delete_expired_key_offices():
#     with SessionLocal() as db:
#         one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)
#         db.query(User).filter(User.created_at < one_week_ago).delete()
#         db.commit()

# scheduler = BackgroundScheduler()
# scheduler.add_job(delete_expired_key_offices, 'interval', hours=24)  # chạy mỗi ngày
# scheduler.start()

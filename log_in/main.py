from fastapi import FastAPI, Form, Request,UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.database import SessionLocal
from app.models import User, GmailLog
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import random, smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone
import traceback
import shutil
import os
from ultralytics import YOLO
import cv2
import zipfile
import tempfile
from fastapi.responses import PlainTextResponse
app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 🔧 SMTP config
SENDER_EMAIL = "huyozil1234@gmail.com"
SENDER_PASSWORD = "qobsxxoijobnqhrl"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Hàm gửi OTP
def send_otp_email(to_email: str, otp_code: str):
    subject = "Your OTP Code"
    body = f"Your OTP is: {otp_code}. It will expire in 60 seconds."
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        print("✅ OTP sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

@app.get("/", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    gmail: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        db.close()
        return templates.TemplateResponse("login.html", {"request": request, "error": "Sai username hoặc mật khẩu!"})

    # ✅ Đúng tài khoản -> sinh OTP
    otp_code = str(random.randint(100000, 999999))
    expired_at = datetime.now(timezone.utc) + timedelta(seconds=60)

    otp_log = GmailLog(
        gmail=gmail,
        otp_code=otp_code,
        created_at=datetime.now(timezone.utc),
        expired_at=expired_at
    )
    db.add(otp_log)
    db.commit()
    db.close()

    # Gửi email OTP
    send_otp_email(gmail, otp_code)

    # ✅ Redirect sang verify OTP
    return RedirectResponse(url=f"/verify-otp?gmail={gmail}", status_code=302)

@app.get("/verify-otp", response_class=HTMLResponse)
async def verify_otp_form(request: Request, gmail: str):
    return templates.TemplateResponse("verify_otp.html", {"request": request, "gmail": gmail})

app.mount("/static", StaticFiles(directory="static"), name="static")

# Load YOLO model
model = YOLO("best.pt")
@app.post("/verify-otp")
async def verify_otp(request: Request, gmail: str = Form(...), otp: str = Form(...)):
    db = SessionLocal()
    try:
        otp_entry = (
            db.query(GmailLog)
            .filter(GmailLog.gmail == gmail)
            .order_by(GmailLog.created_at.desc())
            .first()
        )

        if not otp_entry:
            return PlainTextResponse("OTP không hợp lệ", status_code=400)

        saved_expired = otp_entry.expired_at
        if saved_expired.tzinfo is None:
            saved_expired = saved_expired.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        if now > saved_expired:
            db.delete(otp_entry)
            db.commit()
            return PlainTextResponse("OTP đã hết thời gian, vui lòng yêu cầu mã mới", status_code=400)

        if otp_entry.otp_code != otp:
            return PlainTextResponse("OTP không hợp lệ", status_code=400)

        # ✅ OTP đúng → sang trang upload ảnh
        return RedirectResponse(url="/upload-image", status_code=302)

    except Exception as e:
        traceback.print_exc()
        return PlainTextResponse(f"Lỗi server: {e}", status_code=500)
    finally:
        db.close()
    
@app.get("/upload-image", response_class=HTMLResponse)
async def upload_image_form(request: Request):
    return templates.TemplateResponse("upload_image.html", {"request": request})

@app.post("/upload-zip-json")
async def process_zip_json(file: UploadFile = File(...)):
    # Kiểm tra định dạng
    if not file.filename.endswith(".zip"):
        return JSONResponse(content={"error": "Vui lòng upload file .zip"}, status_code=400)

    # Lưu file zip tạm
    zip_path = os.path.join("static/uploads", file.filename)
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Giải nén vào thư mục tạm
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    # Mapping status
    status_priority = {
        "lv_1": "theo dõi",
        "lv_2": "sửa chữa cùng thiết bị khác",
        "lv_3": "sửa chữa 6-12 tháng",
        "lv_4": "sửa chữa 3-6 tháng",
        "lv_5": "sửa ngay lập tức"
    }
    severity_order = {"lv_1": 1, "lv_2": 2, "lv_3": 3, "lv_4": 4, "lv_5": 5}

    final_results = []

    # Xử lý từng ảnh trong zip
    for root, _, files in os.walk(temp_dir):
        for img_name in files:
            img_path = os.path.join(root, img_name)
            if not img_name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue  # bỏ qua file không phải ảnh

            results = model(img_path)
            detections_list = []
            max_severity = 0

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    label = r.names[cls_id].lower()
                    confidence = float(box.conf[0].item())
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    area = (x2 - x1) * (y2 - y1)

                    detections_list.append({
                        "label": label,
                        "class_id": cls_id,
                        "confidence": round(confidence, 4),
                        "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                        "area": round(area, 1),
                        "status": status_priority.get(label, "không xác định")
                    })

                    if label in severity_order:
                        max_severity = max(max_severity, severity_order[label])

            overall_status = "không xác định"
            for k, v in severity_order.items():
                if v == max_severity:
                    overall_status = status_priority[k]
                    break

            final_results.append({
                "file": img_name,
                "defects": len(detections_list),
                "status": overall_status,
                "detections": detections_list
            })

    return JSONResponse(content=final_results)

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

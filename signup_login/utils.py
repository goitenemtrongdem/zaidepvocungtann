from passlib.context import CryptContext
import smtplib
from email.mime.text import MIMEText

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def send_email(to_email: str, otp_code: str):
    sender_email = "huyozil1234@gmail.com"
    sender_password = "qobsxxoijobnqhrl"

    msg = MIMEText(f"Your OTP code is: {otp_code}. It will expire in 60 seconds.")
    msg["Subject"] = "Your OTP Code"
    msg["From"] = sender_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)

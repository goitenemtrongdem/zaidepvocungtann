from fastapi import FastAPI
from .database import Base, engine
from . import models
from .auth import router as auth_router

# Tạo bảng nếu chưa có
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Đăng ký router
app.include_router(auth_router)

"""FastAPI アプリの組み立て(設定の読み込み・CORS・ルーターの登録)。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health

settings = get_settings()

app = FastAPI(title="jelgram API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)

app.include_router(health.router)

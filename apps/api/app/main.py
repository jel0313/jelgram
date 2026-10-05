"""FastAPI アプリの組み立て(設定の読み込み・CORS・ルーターの登録)。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.health.router import router as health_router
from app.posts.router import router as posts_router

settings = get_settings()

app = FastAPI(title="jelgram API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(posts_router)

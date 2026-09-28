"""認証の API(ログイン中のユーザー情報。認証の確認用)。"""

from fastapi import APIRouter

from app.auth.dependencies import CurrentUserDep
from app.auth.schemas import CurrentUser

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUserDep) -> CurrentUser:
    """トークンで特定したユーザーを返す。DB には接続しない。"""
    return user

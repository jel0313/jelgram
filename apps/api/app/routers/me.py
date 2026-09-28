"""ログイン中のユーザー情報 API(認証の確認用)。"""

from fastapi import APIRouter

from app.auth import CurrentUser, CurrentUserDep

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUserDep) -> CurrentUser:
    """トークンで特定したユーザーを返す。DB には接続しない。"""
    return user

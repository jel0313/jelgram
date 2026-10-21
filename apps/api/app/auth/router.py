"""認証の API(ログアウト = トークンの失効)。"""

from fastapi import APIRouter, status

from app.auth import service
from app.auth.dependencies import CurrentUserDep
from app.core.redis import RedisDep
from app.core.schemas import COMMON_ERROR_RESPONSES

router = APIRouter(prefix="/auth", tags=["auth"], responses=COMMON_ERROR_RESPONSES)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUserDep, redis: RedisDep) -> None:
    """今のトークンを失効させる(6-5)。

    Supabase のログアウトはリフレッシュトークンを無効にするが、発行済みのアクセストークンは
    期限(1時間)まで使えてしまう。そこで、セッション ID を期限まで Redis の失効リストに入れる。
    """
    service.logout(redis, user)

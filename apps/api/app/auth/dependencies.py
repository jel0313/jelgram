"""認証・認可の依存関数。

各エンドポイントは引数に `user: CurrentUserDep` と書くだけで、ログイン必須になる。

    Authorization: Bearer <JWT>
      ↓ ① 署名・期限・発行元・audience を検証(Supabase の公開鍵 JWKS)
      ↓ ② ログアウト済みのセッションでないか(Redis の失効リスト。6-5)
      ↓ ③ アカウントの状態(凍結・退会)とロールを DB から読む(7-5)
    CurrentUser
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from redis import RedisError

from app.auth import repository
from app.auth.constants import JWT_ALGORITHMS, JWT_AUDIENCE, REVOKED_SESSION_KEY
from app.auth.exceptions import AccountSuspendedError, InvalidTokenError
from app.auth.schemas import CurrentUser, Role
from app.core import rate_limit as rate_limit_core
from app.core.config import Settings, SettingsDep, get_settings
from app.core.db import DbSessionDep
from app.core.exceptions import (
    ForbiddenError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.core.redis import RedisDep

logger = logging.getLogger(__name__)

# Authorization: Bearer <トークン> を取り出す。/docs の Authorize ボタンもこれで表示される
bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_jwks_client() -> jwt.PyJWKClient:
    """Supabase の公開鍵(JWKS)を取得するクライアントを返す。

    取得した公開鍵はクライアントの中でキャッシュされるため、アプリ全体で1つを使い回す。
    """
    settings = get_settings()
    return jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", timeout=5)


def decode_token(token: str, jwks_client: jwt.PyJWKClient, settings: Settings) -> dict[str, Any]:
    """JWT の署名と中身を検証して、クレーム(中身)を返す。"""
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError as e:
        raise ServiceUnavailableError("認証サーバーに接続できません") from e
    except (jwt.PyJWKClientError, jwt.InvalidTokenError) as e:
        raise InvalidTokenError from e

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=JWT_ALGORITHMS,  # トークン側の alg は信じない
            audience=JWT_AUDIENCE,
            issuer=f"{settings.supabase_url}/auth/v1",
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError from e
    return claims


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    jwks_client: Annotated[jwt.PyJWKClient, Depends(get_jwks_client)],
    settings: SettingsDep,
    session: DbSessionDep,
    redis: RedisDep,
) -> CurrentUser:
    """JWT を検証し、ログイン中のユーザーを返す。

    公開鍵の取得・DB でブロックする通信を行うため、async def にしない(11-1)。
    """
    if credentials is None:
        raise UnauthorizedError
    claims = decode_token(credentials.credentials, jwks_client, settings)

    session_id = claims.get("session_id")
    if session_id and _is_revoked(redis, session_id):
        raise InvalidTokenError("ログアウト済みのトークンです")

    try:
        user = CurrentUser(
            id=claims["sub"],
            email=claims.get("email"),
            session_id=session_id,
            expires_at=datetime.fromtimestamp(claims["exp"], UTC),
        )
    except (ValidationError, ValueError) as e:
        raise InvalidTokenError from e

    account = repository.get_account(session, user.id)
    if account is None or account.status == "deleted":
        raise InvalidTokenError("ユーザーが見つかりません")
    if account.status == "suspended":
        raise AccountSuspendedError
    user.role = account.role
    return user


def _is_revoked(redis: Any, session_id: str) -> bool:
    """失効リストにあるか。Redis が落ちていたら確認できないので通す(ログに残す)。"""
    try:
        return bool(redis.exists(REVOKED_SESSION_KEY.format(session_id=session_id)))
    except RedisError:
        logger.warning("Redis に接続できないため、トークン失効の確認をスキップしました")
        return False


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_role(*roles: Role) -> Callable[[CurrentUser], CurrentUser]:
    """指定したロールのユーザーだけを通す依存関数を作る(7-5)。

    使い方:`admin: Annotated[CurrentUser, Depends(require_role("admin"))]`
    """

    def dependency(user: CurrentUserDep) -> CurrentUser:
        if user.role not in roles:
            raise ForbiddenError("管理者だけが使える操作です")
        return user

    return dependency


AdminUserDep = Annotated[CurrentUser, Depends(require_role("admin"))]


def rate_limit(name: str, setting: str, window_seconds: int = 60) -> Callable[..., None]:
    """ユーザーごとのレート制限をかける依存関数を作る(8-3)。

    上限は設定(Settings)の項目名で指定する。例:rate_limit("posts", "rate_limit_posts_per_minute")
    使い方:`@router.post(..., dependencies=[Depends(rate_limit(...))])`
    """

    def dependency(user: CurrentUserDep, redis: RedisDep, settings: SettingsDep) -> None:
        limit: int = getattr(settings, setting)
        result = rate_limit_core.hit(redis, f"{name}:{user.id}", limit, window_seconds)
        if not result.allowed:
            raise RateLimitError(retry_after=result.retry_after)

    return dependency

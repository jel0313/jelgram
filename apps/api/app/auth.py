"""認証(Supabase が発行した JWT の検証)。

各エンドポイントは引数に `user: CurrentUserDep` と書くだけで、認証が必須になる。
"""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings

# 許可する署名方式。トークン側の alg は信じない
JWT_ALGORITHMS = ["ES256"]
# ログイン済みユーザー向けのトークンだけを通す
JWT_AUDIENCE = "authenticated"

# Authorization: Bearer <トークン> を取り出す。/docs の Authorize ボタンもこれで表示される
bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """ログイン中のユーザー。"""

    id: UUID
    email: str | None = None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


@lru_cache
def get_jwks_client() -> jwt.PyJWKClient:
    """Supabase の公開鍵(JWKS)を取得するクライアントを返す。

    取得した公開鍵はクライアントの中でキャッシュされるため、アプリ全体で1つを使い回す。
    """
    settings = get_settings()
    return jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", timeout=5)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    jwks_client: Annotated[jwt.PyJWKClient, Depends(get_jwks_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    """JWT を検証し、ログイン中のユーザーを返す。

    公開鍵の取得でブロックする通信を行うため、async def にしない。
    """
    if credentials is None:
        raise _unauthorized("認証が必要です")
    token = credentials.credentials

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError as e:
        raise HTTPException(status_code=503, detail="認証サーバーに接続できません") from e
    except (jwt.PyJWKClientError, jwt.InvalidTokenError) as e:
        raise _unauthorized("トークンが無効です") from e

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=JWT_ALGORITHMS,
            audience=JWT_AUDIENCE,
            issuer=f"{settings.supabase_url}/auth/v1",
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
        return CurrentUser(id=claims["sub"], email=claims.get("email"))
    except (jwt.InvalidTokenError, ValidationError) as e:
        raise _unauthorized("トークンが無効です") from e


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]

"""認証の依存関数(Supabase が発行した JWT の検証)。

各エンドポイントは引数に `user: CurrentUserDep` と書くだけで、認証が必須になる。
"""

from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from app.auth.constants import JWT_ALGORITHMS, JWT_AUDIENCE
from app.auth.schemas import CurrentUser
from app.core.config import SettingsDep, get_settings

# Authorization: Bearer <トークン> を取り出す。/docs の Authorize ボタンもこれで表示される
bearer_scheme = HTTPBearer(auto_error=False)


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
    settings: SettingsDep,
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

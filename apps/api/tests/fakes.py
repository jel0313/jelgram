"""テスト用の偽物(外部サービスの代わり)。本物と同じメソッドを持つ。"""

import io
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from PIL import Image

from app.chat.ai_client import AIMessage, AIResult, AIStreamChunk
from app.chat.exceptions import AIUnavailableError

SUPABASE_URL = "https://test.supabase.co"


class FakeStorage:
    """メモリの中に保存するストレージ。"""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.deleted: list[str] = []
        self.fail = False

    def _check(self) -> None:
        if self.fail:
            from app.media.storage import StorageError

            raise StorageError

    def upload(self, path: str, data: bytes, content_type: str, *, upsert: bool = False) -> None:
        self._check()
        if path in self.objects and not upsert:
            raise AssertionError(f"上書きしようとした:{path}")
        self.objects[path] = (data, content_type)

    def download(self, path: str) -> bytes:
        self._check()
        if path not in self.objects:
            from app.media.storage import StorageError

            raise StorageError
        return self.objects[path][0]

    def delete(self, paths: list[str]) -> None:
        self._check()
        for path in paths:
            self.objects.pop(path, None)
            self.deleted.append(path)

    def signed_urls(self, paths: list[str], expires_in: int) -> dict[str, str]:
        self._check()
        return {p: f"https://storage.test/{p}?token=signed" for p in paths if p in self.objects}

    def signed_upload_url(self, path: str) -> str:
        self._check()
        return f"https://storage.test/upload/{path}?token=upload"


@dataclass
class FakeAI:
    """決まった答えを返す AI。受け取った内容を記録する。"""

    reply: str = "それな。でも次はもっと具体的に頼むわ。"
    blocked: bool = False
    fail: bool = False
    calls: list[tuple[str, list[AIMessage]]] = field(default_factory=list)

    def generate(self, system: str, messages: list[AIMessage]) -> AIResult:
        self.calls.append((system, messages))
        if self.fail:
            raise AIUnavailableError
        return AIResult(
            text=self.reply, prompt_tokens=10, completion_tokens=5, blocked=self.blocked
        )

    def stream(self, system: str, messages: list[AIMessage]) -> Iterator[AIStreamChunk]:
        self.calls.append((system, messages))
        if self.fail:
            raise AIUnavailableError
        half = len(self.reply) // 2
        yield AIStreamChunk(text=self.reply[:half])
        yield AIStreamChunk(text=self.reply[half:])
        yield AIStreamChunk(
            result=AIResult(
                text=self.reply, prompt_tokens=10, completion_tokens=5, blocked=self.blocked
            )
        )


class FakePush:
    def __init__(self, invalid_endpoints: set[str] | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self.invalid = invalid_endpoints or set()

    def send(self, subscription: dict[str, Any], payload: dict[str, Any]) -> bool:
        if subscription["endpoint"] in self.invalid:
            return False
        self.sent.append(payload)
        return True


# ---------------------------------------------------------------- JWT(本物と同じ ES256 で署名する)


_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


class FakeJWKSClient:
    """Supabase の JWKS の代わりに、テスト用の公開鍵を返す。"""

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        header = jwt.get_unverified_header(token)
        if header.get("kid") != "test-key":
            raise jwt.PyJWKClientError("鍵がない")
        return jwt.PyJWK.from_dict(
            {
                **jwt.algorithms.ECAlgorithm.to_jwk(_PRIVATE_KEY.public_key(), as_dict=True),
                "alg": "ES256",
            }
        )


def make_token(
    user_id: UUID | str,
    *,
    session_id: str = "session-1",
    expires_in: int = 3600,
    **overrides: Any,
) -> str:
    now = int(time.time())
    claims = {
        "sub": str(user_id),
        "email": f"{user_id}@example.com",
        "aud": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "iat": now,
        "exp": now + expires_in,
        "session_id": session_id,
        **overrides,
    }
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="ES256", headers={"kid": "test-key"})


# ---------------------------------------------------------------- 画像


def make_image(
    fmt: str = "PNG", size: tuple[int, int] = (40, 30), *, exif: bytes | None = None
) -> bytes:
    image = Image.new("RGB", size, color=(200, 100, 50))
    buffer = io.BytesIO()
    kwargs: dict[str, Any] = {}
    if exif is not None:
        kwargs["exif"] = exif
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()

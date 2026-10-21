"""ミドルウェア(全リクエストの前後に必ず通る処理)。

FastAPI の `@app.middleware("http")` ではなく、素の ASGI で書いている。
理由:BaseHTTPMiddleware はストリーミング応答(SSE)や contextvars と相性が悪いため。

    リクエスト → RequestContext → SecurityHeaders → BodySizeLimit → CORS → ルーター
"""

import contextlib
import logging
import re
import time
import uuid
from collections.abc import Callable

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import metrics
from app.core.logging import request_id_var

access_logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.error")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class RequestContextMiddleware:
    """リクエスト ID・アクセスログ・処理時間・メトリクス・想定外エラーの 500 化。

    15-2・15-3・5-5・22-1
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # クライアントが付けてきた ID は形をチェックしてから使う(ログの汚染を防ぐ)
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _REQUEST_ID_PATTERN.match(incoming) else uuid.uuid4().hex
        request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        start = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # 想定外のエラー:中身(スタックトレース)はログにだけ出し、利用者には出さない(5-5)
            error_logger.exception("想定外のエラー", extra={"path": scope["path"]})
            if response_started:
                raise
            status_code = 500
            response = JSONResponse(
                {
                    "code": "internal_error",
                    "message": "サーバーでエラーが発生しました",
                    "details": {"request_id": request_id},
                },
                status_code=500,
            )
            await response(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            route = scope.get("route")
            path_template = getattr(route, "path", "unmatched")
            metrics.observe_request(scope["method"], path_template, status_code, duration)
            access_logger.info(
                "access",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "route": path_template,
                    "status": status_code,
                    "duration_ms": round(duration * 1000, 1),
                    "client_ip": (scope.get("client") or ("-",))[0],
                },
            )


# /docs と /redoc は CDN の JS・CSS を読むので、その分だけ CSP をゆるめる
_DOCS_CSP = (
    "default-src 'none'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
)
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


class SecurityHeadersMiddleware:
    """セキュリティヘッダーを全レスポンスに付ける(8-2)。"""

    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_docs = scope["path"] in ("/docs", "/redoc", "/docs/oauth2-redirect")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"  # MIME タイプの推測をさせない
                headers["X-Frame-Options"] = "DENY"  # iframe に埋め込ませない
                headers["Referrer-Policy"] = "no-referrer"  # 遷移先に URL を渡さない
                headers["Content-Security-Policy"] = _DOCS_CSP if is_docs else _API_CSP
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                if not is_docs:
                    headers.setdefault(
                        "Cache-Control", "no-store"
                    )  # 個人データをキャッシュさせない
                if self.hsts:  # HTTPS で動く本番だけ
                    headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_wrapper)


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """リクエスト本文のサイズに上限をかける(8-7)。超えたら 413。

    Content-Length を見るだけでは、ヘッダーを偽る・付けない(chunked)送信を止められない。
    そのため、実際に受け取ったバイト数も数える。
    """

    def __init__(
        self, app: ASGIApp, *, default_limit: int, limit_for: Callable[[str], int | None]
    ) -> None:
        self.app = app
        self.default_limit = default_limit
        self.limit_for = limit_for  # パスごとに上限を変えたいとき(画像アップロードなど)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self.limit_for(scope["path"]) or self.default_limit
        content_length = dict(scope["headers"]).get(b"content-length")
        if content_length is not None and content_length.isdigit() and int(content_length) > limit:
            await self._reject(scope, receive, send, limit)
            return

        received = 0
        too_large = False

        async def receive_wrapper() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_large = True
                    raise _BodyTooLarge
            return message

        async def send_wrapper(message: Message) -> None:
            # 上限を超えた後にアプリが返す応答(FastAPI は 400 にする)は捨てて、413 に置き換える
            if too_large:
                return
            await send(message)

        with contextlib.suppress(_BodyTooLarge):
            await self.app(scope, receive_wrapper, send_wrapper)
        if too_large:
            await self._reject(scope, receive, send, limit)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, limit: int) -> None:
        response = JSONResponse(
            {
                "code": "payload_too_large",
                "message": "送信データが大きすぎます",
                "details": {"limit_bytes": limit},
            },
            status_code=413,
        )
        await response(scope, receive, send)

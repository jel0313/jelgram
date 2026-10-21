"""アプリ共通の例外(5-2)。

各機能の例外(PostNotFoundError など)は、これを継承して `exceptions.py` に置く。
例外ハンドラー(core/error_handlers.py)が、どれも同じ形のレスポンスにする(5-3)。

    {"code": "post_not_found", "message": "投稿が見つかりません", "details": null}
"""

from typing import Any


class AppError(Exception):
    """アプリの例外の親。status_code・code・message を子クラスで決める。"""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "サーバーでエラーが発生しました"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        self.headers = headers
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "リクエストが正しくありません"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "認証が必要です"

    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        super().__init__(message, details=details, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "この操作は許可されていません"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "見つかりません"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "ほかの操作と競合しました"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"
    message = "送信データが大きすぎます"


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "unsupported_media_type"
    message = "この形式のファイルは使えません"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "操作が多すぎます。少し時間をおいてください"

    def __init__(self, message: str | None = None, *, retry_after: int | None = None) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(message, headers=headers)


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "一時的に利用できません。時間をおいてもう一度お試しください"

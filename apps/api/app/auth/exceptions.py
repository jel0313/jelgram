"""認証のエラー。"""

from app.core.exceptions import ForbiddenError, UnauthorizedError


class InvalidTokenError(UnauthorizedError):
    code = "invalid_token"
    message = "トークンが無効です"


class AccountSuspendedError(ForbiddenError):
    code = "account_suspended"
    message = "このアカウントは利用停止中です"

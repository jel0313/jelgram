"""ユーザーのエラー。"""

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError


class UserNotFoundError(NotFoundError):
    code = "user_not_found"
    message = "ユーザーが見つかりません"


class UsernameTakenError(ConflictError):
    code = "username_taken"
    message = "このユーザー名はすでに使われています"


class CannotFollowSelfError(BadRequestError):
    code = "cannot_follow_self"
    message = "自分はフォロー・ブロックできません"


class FollowRequestNotFoundError(NotFoundError):
    code = "follow_request_not_found"
    message = "フォローリクエストが見つかりません"

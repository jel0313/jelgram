"""投稿のエラー。"""

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError


class PostNotFoundError(NotFoundError):
    code = "post_not_found"
    message = "投稿が見つかりません"


class NotPostOwnerError(ForbiddenError):
    code = "not_post_owner"
    message = "自分の投稿だけ編集・削除できます"


class PostVersionConflictError(ConflictError):
    code = "post_version_conflict"
    message = "ほかの画面で更新されています。読み込み直してから編集してください"


class ContentNotAllowedError(BadRequestError):
    code = "content_not_allowed"
    message = "投稿できない言葉が含まれています"

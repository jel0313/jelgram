"""コメントのエラー。"""

from app.core.exceptions import ForbiddenError, NotFoundError


class CommentNotFoundError(NotFoundError):
    code = "comment_not_found"
    message = "コメントが見つかりません"


class NotCommentOwnerError(ForbiddenError):
    code = "not_comment_owner"
    message = "このコメントは編集・削除できません"


class CommentsDisabledError(ForbiddenError):
    code = "comments_disabled"
    message = "この投稿はコメントできません"

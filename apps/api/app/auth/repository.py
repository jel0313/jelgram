"""認証の DB アクセス。"""

from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.orm import Session


def get_account(session: Session, user_id: UUID) -> Row[tuple[str, str]] | None:
    """アカウントのロールと状態を返す。いなければ None。"""
    sql = text("select role, status from profiles where id = :id")
    return session.execute(sql, {"id": user_id}).one_or_none()

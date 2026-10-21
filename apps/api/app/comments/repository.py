"""コメントの DB アクセス。"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.core.visibility import can_view_content_of, not_blocked, post_is_alive


def get_visible_post(session: Session, post_id: int, viewer_id: UUID) -> RowMapping | None:
    """コメントを付ける・読む対象の投稿(閲覧者が見てよいものだけ)。"""
    sql = text(f"""
        select p.id, p.user_id, p.comments_disabled
        from posts p join profiles a on a.id = p.user_id
        where p.id = :post_id and {post_is_alive("p")} and {can_view_content_of("a")}
    """)
    return (
        session.execute(sql, {"post_id": post_id, "viewer_id": viewer_id}).mappings().one_or_none()
    )


_SELECT = """
    select c.id, c.post_id, c.content, c.created_at, c.updated_at, c.user_id,
           p.user_id as post_owner_id,
           a.id as author_id, a.username as author_username,
           a.display_name as author_display_name, a.avatar_url as author_avatar_url
    from comments c
    join posts p on p.id = c.post_id
    join profiles a on a.id = c.user_id
"""


def list_comments(
    session: Session, post_id: int, viewer_id: UUID, after_id: int | None, limit: int
) -> Sequence[RowMapping]:
    """投稿のコメントを古い順に。ブロック関係にある人のコメントは出さない(7-4)。"""
    sql = text(f"""
        {_SELECT}
        where c.post_id = :post_id and c.deleted_at is null and a.status = 'active'
          and {not_blocked("a")}
          and (cast(:after_id as bigint) is null or c.id > cast(:after_id as bigint))
        order by c.id
        limit :limit
    """)
    params = {"post_id": post_id, "viewer_id": viewer_id, "after_id": after_id, "limit": limit + 1}
    return session.execute(sql, params).mappings().all()


def get_comment(session: Session, comment_id: int) -> RowMapping | None:
    sql = text(f"{_SELECT} where c.id = :id and c.deleted_at is null and p.deleted_at is null")
    return session.execute(sql, {"id": comment_id}).mappings().one_or_none()


def insert_comment(session: Session, post_id: int, user_id: UUID, content: str) -> int:
    comment_id: int = session.execute(
        text("""
            insert into comments (post_id, user_id, content) values (:p, :u, :c) returning id
        """),
        {"p": post_id, "u": user_id, "c": content},
    ).scalar_one()
    session.execute(
        text("update posts set comment_count = comment_count + 1 where id = :id"), {"id": post_id}
    )
    return comment_id


def update_comment(session: Session, comment_id: int, content: str) -> None:
    session.execute(
        text("update comments set content = :c where id = :id"), {"id": comment_id, "c": content}
    )


def soft_delete_comment(session: Session, comment_id: int, post_id: int) -> None:
    deleted = session.execute(
        text("""
            update comments set deleted_at = now()
            where id = :id and deleted_at is null returning id
        """),
        {"id": comment_id},
    ).one_or_none()
    if deleted is not None:
        session.execute(
            text("""
                update posts set comment_count = greatest(comment_count - 1, 0) where id = :id
            """),
            {"id": post_id},
        )

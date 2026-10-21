"""画像の DB アクセス。"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.core.visibility import can_view_content_of, not_blocked, post_is_alive

_COLUMNS = """
    m.id, m.owner_id, m.path, m.thumbnail_path, m.content_type, m.size_bytes,
    m.width, m.height, m.status, m.created_at
"""


def insert_media(session: Session, **values: Any) -> RowMapping:
    sql = text(f"""
        insert into media as m (owner_id, path, content_type, size_bytes, width, height)
        values (:owner_id, :path, :content_type, :size_bytes, :width, :height)
        returning {_COLUMNS}
    """)
    return session.execute(sql, values).mappings().one()


def get_media(session: Session, media_id: UUID) -> RowMapping | None:
    sql = text(f"select {_COLUMNS} from media m where m.id = :id")
    return session.execute(sql, {"id": media_id}).mappings().one_or_none()


def get_visible_media(session: Session, media_id: UUID, viewer_id: UUID) -> RowMapping | None:
    """閲覧者が見てよい画像だけを返す(9-6)。

    見てよい = 自分の画像 / 見てよい投稿の画像 / ブロック関係にない人のアイコン / 見てよいストーリー
    """
    sql = text(f"""
        select {_COLUMNS} from media m
        where m.id = :id and (
            m.owner_id = :viewer_id
            or exists (
                select 1 from post_media pm
                join posts p on p.id = pm.post_id
                join profiles a on a.id = p.user_id
                where pm.media_id = m.id and {post_is_alive("p")} and {can_view_content_of("a")}
            )
            or exists (
                select 1 from profiles a
                where a.avatar_media_id = m.id and a.status = 'active' and {not_blocked("a")}
            )
            or exists (
                select 1 from stories s
                join profiles a on a.id = s.user_id
                where s.media_id = m.id and s.expires_at > now() and {can_view_content_of("a")}
            )
        )
    """)
    return session.execute(sql, {"id": media_id, "viewer_id": viewer_id}).mappings().one_or_none()


def get_owned_unused_media(
    session: Session, media_ids: Sequence[UUID], owner_id: UUID
) -> Sequence[RowMapping]:
    """自分の画像のうち、まだどの投稿にも使われていないものを返す(投稿に付ける前のチェック)。"""
    sql = text(f"""
        select {_COLUMNS} from media m
        where m.id = any(:ids) and m.owner_id = :owner_id and m.status <> 'failed'
          and not exists (select 1 from post_media pm where pm.media_id = m.id)
    """)
    return session.execute(sql, {"ids": list(media_ids), "owner_id": owner_id}).mappings().all()


def update_processed(
    session: Session,
    media_id: UUID,
    *,
    status: str,
    thumbnail_path: str | None = None,
    width: int | None = None,
    height: int | None = None,
    size_bytes: int | None = None,
) -> None:
    sql = text("""
        update media set
            status = :status,
            thumbnail_path = coalesce(:thumbnail_path, thumbnail_path),
            width = coalesce(:width, width),
            height = coalesce(:height, height),
            size_bytes = coalesce(:size_bytes, size_bytes)
        where id = :id
    """)
    session.execute(
        sql,
        {
            "id": media_id,
            "status": status,
            "thumbnail_path": thumbnail_path,
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
        },
    )


def delete_media(session: Session, media_id: UUID) -> None:
    session.execute(text("delete from media where id = :id"), {"id": media_id})

"""ストーリーの業務ロジックと DB アクセス(11-5)。"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import outbox
from app.core.exceptions import NotFoundError
from app.core.visibility import can_view_content_of
from app.media import repository as media_repository
from app.media import service as media_service
from app.media.exceptions import MediaNotUsableError
from app.media.schemas import MediaOut
from app.media.storage import StorageClient
from app.posts.schemas import Author


class StoryNotFoundError(NotFoundError):
    code = "story_not_found"
    message = "ストーリーが見つかりません"


class StoryResponse(BaseModel):
    id: int
    author: Author
    media: MediaOut
    created_at: datetime
    expires_at: datetime


_SELECT = """
    select s.id, s.created_at, s.expires_at,
           a.id as author_id, a.username, a.display_name, a.avatar_url,
           m.id as media_id, m.path, m.thumbnail_path, m.width, m.height
    from stories s
    join profiles a on a.id = s.user_id
    join media m on m.id = s.media_id
"""


def _to_responses(
    storage: StorageClient,
    rows: list[dict[str, Any]],
    expires_in: int,
) -> list[StoryResponse]:
    media_rows = [{**row, "id": row["media_id"]} for row in rows]
    signed = media_service.sign_media(storage, media_rows, expires_in)
    return [
        StoryResponse(
            id=row["id"],
            author=Author(
                id=row["author_id"],
                username=row["username"],
                display_name=row["display_name"],
                avatar_url=row["avatar_url"],
            ),
            media=signed[row["media_id"]],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
        )
        for row in rows
    ]


def create_story(
    session: Session, storage: StorageClient, user_id: UUID, media_id: UUID, expires_in: int
) -> StoryResponse:
    if not media_repository.get_owned_unused_media(session, [media_id], user_id):
        raise MediaNotUsableError
    story_id = session.execute(
        text("insert into stories (user_id, media_id) values (:u, :m) returning id"),
        {"u": user_id, "m": media_id},
    ).scalar_one()
    row = session.execute(text(f"{_SELECT} where s.id = :id"), {"id": story_id}).mappings().one()
    session.commit()
    return _to_responses(storage, [dict(row)], expires_in)[0]


def list_stories(
    session: Session, storage: StorageClient, viewer_id: UUID, expires_in: int
) -> list[StoryResponse]:
    sql = text(f"""
        {_SELECT}
        where s.expires_at > now() and {can_view_content_of("a")}
          and (
              a.id = :viewer_id
              or exists (select 1 from follows f where f.follower_id = :viewer_id
                         and f.followee_id = a.id and f.status = 'accepted')
          )
        order by s.created_at desc
        limit 100
    """)
    rows = [dict(r) for r in session.execute(sql, {"viewer_id": viewer_id}).mappings().all()]
    return _to_responses(storage, rows, expires_in)


def delete_story(session: Session, user_id: UUID, story_id: int) -> None:
    paths = session.execute(
        text("""
            delete from media m using stories s
            where s.media_id = m.id and s.id = :id and s.user_id = :u
            returning m.path, m.thumbnail_path
        """),
        {"id": story_id, "u": user_id},
    ).all()
    if not paths:
        raise StoryNotFoundError
    outbox.enqueue(session, outbox.MEDIA_DELETE, {"paths": [p for row in paths for p in row if p]})
    session.commit()


def expire_stories(session: Session, now: datetime) -> int:
    """期限切れのストーリーを消す(定期ジョブから呼ぶ)。消した件数を返す。"""
    paths = session.execute(
        text("""
            delete from media m using stories s
            where s.media_id = m.id and s.expires_at <= :now
            returning m.path, m.thumbnail_path
        """),
        {"now": now},
    ).all()
    if paths:
        outbox.enqueue(
            session, outbox.MEDIA_DELETE, {"paths": [p for row in paths for p in row if p]}
        )
    session.commit()
    return len(paths)

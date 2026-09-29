"""投稿・いいねの DB アクセス。SQL はこのファイルにだけ書く。

SQL は text() で生のまま書き、値は必ずバインド変数(:post_id など)で渡す。
確定(commit)はしない。確定は service が行う。
"""

from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

# 投稿・投稿者・いいね数・自分がいいね済みか を 1 回で取る SELECT。WHERE・ORDER BY は各関数で足す
_SELECT_POSTS = """
    select
        p.id,
        p.content,
        p.image_url,
        p.created_at,
        pr.id           as author_id,
        pr.display_name as author_display_name,
        pr.avatar_url   as author_avatar_url,
        (select count(*) from likes l where l.post_id = p.id) as like_count,
        exists (
            select 1 from likes l where l.post_id = p.id and l.user_id = :user_id
        ) as liked_by_me
    from posts p
    join profiles pr on pr.id = p.user_id
"""


def find_timeline(session: Session, user_id: UUID, limit: int) -> list[Row]:
    """新しい順(同じ時刻なら id の大きい順)に、最大 limit 件を取る。"""
    sql = text(_SELECT_POSTS + "order by p.created_at desc, p.id desc limit :limit")
    return list(session.execute(sql, {"user_id": user_id, "limit": limit}).all())


def find_post_row(session: Session, post_id: int, user_id: UUID) -> Row:
    """投稿 1 件を、タイムラインと同じ形で取る。"""
    sql = text(_SELECT_POSTS + "where p.id = :post_id")
    return session.execute(sql, {"user_id": user_id, "post_id": post_id}).one()


def exists_post(session: Session, post_id: int) -> bool:
    sql = text("select exists (select 1 from posts where id = :post_id)")
    return session.execute(sql, {"post_id": post_id}).scalar_one()


def insert_post(session: Session, user_id: UUID, content: str, image_url: str | None) -> int:
    """投稿を追加し、DB が振った id を返す(確定はしない)。"""
    sql = text(
        "insert into posts (user_id, content, image_url) "
        "values (:user_id, :content, :image_url) "
        "returning id"
    )
    params = {"user_id": user_id, "content": content, "image_url": image_url}
    return session.execute(sql, params).scalar_one()


def insert_like(session: Session, post_id: int, user_id: UUID) -> None:
    """いいねを追加する。すでにあれば何もしない。"""
    sql = text(
        "insert into likes (user_id, post_id) values (:user_id, :post_id) "
        "on conflict (user_id, post_id) do nothing"
    )
    session.execute(sql, {"user_id": user_id, "post_id": post_id})


def delete_like(session: Session, post_id: int, user_id: UUID) -> None:
    """いいねを削除する。なければ何もしない。"""
    sql = text("delete from likes where user_id = :user_id and post_id = :post_id")
    session.execute(sql, {"user_id": user_id, "post_id": post_id})


def count_likes(session: Session, post_id: int) -> int:
    sql = text("select count(*) from likes where post_id = :post_id")
    return session.execute(sql, {"post_id": post_id}).scalar_one()


def is_liked(session: Session, post_id: int, user_id: UUID) -> bool:
    sql = text(
        "select exists (select 1 from likes where post_id = :post_id and user_id = :user_id)"
    )
    return session.execute(sql, {"post_id": post_id, "user_id": user_id}).scalar_one()

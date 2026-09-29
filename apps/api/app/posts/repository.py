"""投稿・いいねの DB アクセス。SQL はこのファイルにだけ書く。

確定(commit)はしない。確定は service が行う。
"""

from uuid import UUID

from sqlalchemy import Row, Select, delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.posts.models import Like, Post
from app.users.models import Profile


def _post_query(user_id: UUID) -> Select:
    """投稿・投稿者・いいね数・自分がいいね済みか を 1 回の SQL で取る。"""
    like_count = select(func.count()).where(Like.post_id == Post.id).scalar_subquery()
    liked_by_me = exists().where(Like.post_id == Post.id, Like.user_id == user_id)
    return select(
        Post,
        Profile,
        like_count.label("like_count"),
        liked_by_me.label("liked_by_me"),
    ).join(Profile, Post.user_id == Profile.id)


def find_timeline(session: Session, user_id: UUID, limit: int) -> list[Row]:
    """新しい順(同じ時刻なら id の大きい順)に、最大 limit 件を取る。"""
    stmt = _post_query(user_id).order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)
    return list(session.execute(stmt).all())


def find_post_row(session: Session, post_id: int, user_id: UUID) -> Row:
    """投稿 1 件を、タイムラインと同じ形で取る。"""
    return session.execute(_post_query(user_id).where(Post.id == post_id)).one()


def exists_post(session: Session, post_id: int) -> bool:
    return session.get(Post, post_id) is not None


def insert_post(session: Session, user_id: UUID, content: str, image_url: str | None) -> Post:
    """投稿を追加する。flush で DB に送り、DB が振った id を受け取る(確定はしない)。"""
    post = Post(user_id=user_id, content=content, image_url=image_url)
    session.add(post)
    session.flush()
    return post


def insert_like(session: Session, post_id: int, user_id: UUID) -> None:
    """いいねを追加する。すでにあれば何もしない。"""
    session.execute(insert(Like).values(user_id=user_id, post_id=post_id).on_conflict_do_nothing())


def delete_like(session: Session, post_id: int, user_id: UUID) -> None:
    """いいねを削除する。なければ何もしない。"""
    session.execute(delete(Like).where(Like.user_id == user_id, Like.post_id == post_id))


def count_likes(session: Session, post_id: int) -> int:
    return session.scalar(select(func.count()).select_from(Like).where(Like.post_id == post_id))


def is_liked(session: Session, post_id: int, user_id: UUID) -> bool:
    return session.scalar(select(exists().where(Like.post_id == post_id, Like.user_id == user_id)))

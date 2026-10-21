"""ユーザー・フォロー・ブロックの DB アクセス。"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.core.visibility import not_blocked

# ---------------------------------------------------------------- プロフィール


def get_profile_base(session: Session, user_id: UUID) -> RowMapping | None:
    """閲覧者によらないプロフィールの情報(キャッシュできる部分。13-1)。"""
    sql = text("""
        select a.id, a.username, a.display_name, a.avatar_url, am.path as avatar_path,
               a.bio, a.is_private, a.created_at,
               (select count(*) from follows f where f.followee_id = a.id and f.status = 'accepted')
                   as follower_count,
               (select count(*) from follows f where f.follower_id = a.id and f.status = 'accepted')
                   as following_count,
               (select count(*) from posts p
                where p.user_id = a.id and p.deleted_at is null and p.hidden_at is null)
                   as post_count
        from profiles a left join media am on am.id = a.avatar_media_id
        where a.id = :id and a.status = 'active'
    """)
    return session.execute(sql, {"id": user_id}).mappings().one_or_none()


def find_user_id_by_username(session: Session, username: str, viewer_id: UUID) -> UUID | None:
    """ユーザー名から id を引く。ブロック関係にある相手は「いない」扱い(7-4)。"""
    sql = text(f"""
        select a.id from profiles a
        where a.username = :username and a.status = 'active' and {not_blocked("a")}
    """)
    user_id: UUID | None = session.execute(
        sql, {"username": username.lower(), "viewer_id": viewer_id}
    ).scalar_one_or_none()
    return user_id


def get_relation(session: Session, viewer_id: UUID, target_id: UUID) -> RowMapping:
    """閲覧者と相手の関係(フォローの状態・ブロック)。"""
    sql = text("""
        select
            (select status from follows
             where follower_id = :v and followee_id = :t) as follow_status,
            exists (select 1 from follows where follower_id = :t and followee_id = :v
                    and status = 'accepted') as follows_me,
            exists (select 1 from blocks where blocker_id = :v and blocked_id = :t) as blocked_by_me
    """)
    return session.execute(sql, {"v": viewer_id, "t": target_id}).mappings().one()


def get_me(session: Session, user_id: UUID) -> RowMapping | None:
    sql = text("""
        select a.id, a.username, a.display_name, a.avatar_url, am.path as avatar_path,
               a.bio, a.is_private, a.role, a.created_at, u.email
        from profiles a
        join auth.users u on u.id = a.id
        left join media am on am.id = a.avatar_media_id
        where a.id = :id
    """)
    return session.execute(sql, {"id": user_id}).mappings().one_or_none()


def update_profile(session: Session, user_id: UUID, values: dict[str, Any]) -> None:
    allowed = {"username", "display_name", "bio", "is_private", "avatar_media_id"}
    sets = ", ".join(f"{column} = :{column}" for column in values if column in allowed)
    session.execute(text(f"update profiles set {sets} where id = :id"), {"id": user_id, **values})


def get_email_target(session: Session, user_id: UUID) -> RowMapping | None:
    """メールの宛先(メールアドレスと表示名)。"""
    sql = text("""
        select u.email, a.display_name from profiles a join auth.users u on u.id = a.id
        where a.id = :id and a.status = 'active'
    """)
    return session.execute(sql, {"id": user_id}).mappings().one_or_none()


def get_avatar(session: Session, user_id: UUID) -> RowMapping | None:
    sql = text("""
        select m.id, m.path, m.thumbnail_path from profiles a
        join media m on m.id = a.avatar_media_id where a.id = :id
    """)
    return session.execute(sql, {"id": user_id}).mappings().one_or_none()


def search_users(
    session: Session, viewer_id: UUID, query_pattern: str, limit: int
) -> Sequence[RowMapping]:
    """ユーザー名・表示名の部分一致(4-3)。pg_trgm のインデックスが効く。"""
    sql = text(f"""
        select a.id, a.username, a.display_name, a.avatar_url, a.is_private
        from profiles a
        where a.status = 'active' and {not_blocked("a")}
          and (a.username ilike :pattern escape '\\' or a.display_name ilike :pattern escape '\\')
        order by (a.username = lower(:raw)) desc, a.username
        limit :limit
    """)
    raw = query_pattern.strip("%")
    return (
        session.execute(
            sql, {"viewer_id": viewer_id, "pattern": query_pattern, "raw": raw, "limit": limit}
        )
        .mappings()
        .all()
    )


# ---------------------------------------------------------------- フォロー(3-7・7-3)


def insert_follow(session: Session, follower_id: UUID, followee_id: UUID, status: str) -> bool:
    """フォローする。すでにフォロー(申請)済みなら False。"""
    row = session.execute(
        text("""
            insert into follows (follower_id, followee_id, status) values (:a, :b, :s)
            on conflict do nothing returning follower_id
        """),
        {"a": follower_id, "b": followee_id, "s": status},
    ).one_or_none()
    return row is not None


def delete_follow(session: Session, follower_id: UUID, followee_id: UUID) -> None:
    session.execute(
        text("delete from follows where follower_id = :a and followee_id = :b"),
        {"a": follower_id, "b": followee_id},
    )


def lock_follow_request(session: Session, follower_id: UUID, followee_id: UUID) -> bool:
    """承認待ちのリクエストを、行ロックをかけて取る(10-3 悲観的ロック)。

    `for update` で、承認と取り消しが同時に来ても、片方が終わるまでもう片方は待つ。
    """
    row = session.execute(
        text("""
            select 1 from follows
            where follower_id = :a and followee_id = :b and status = 'pending'
            for update
        """),
        {"a": follower_id, "b": followee_id},
    ).one_or_none()
    return row is not None


def accept_follow(session: Session, follower_id: UUID, followee_id: UUID) -> None:
    session.execute(
        text("""
            update follows set status = 'accepted'
            where follower_id = :a and followee_id = :b and status = 'pending'
        """),
        {"a": follower_id, "b": followee_id},
    )


def accept_all_pending(session: Session, followee_id: UUID) -> None:
    """非公開をやめたら、承認待ちを全部承認する。"""
    session.execute(
        text(
            "update follows set status = 'accepted' where followee_id = :b and status = 'pending'"
        ),
        {"b": followee_id},
    )


def list_follow_requests(session: Session, user_id: UUID) -> Sequence[RowMapping]:
    sql = text("""
        select a.id, a.username, a.display_name, a.avatar_url, f.created_at
        from follows f join profiles a on a.id = f.follower_id
        where f.followee_id = :u and f.status = 'pending' and a.status = 'active'
        order by f.created_at
    """)
    return session.execute(sql, {"u": user_id}).mappings().all()


def list_follow_users(
    session: Session, user_id: UUID, direction: str, limit: int, offset: int
) -> tuple[Sequence[RowMapping], int]:
    """フォロワー(direction=followers)・フォロー中(following)の一覧と総件数。"""
    me, other = (
        ("followee_id", "follower_id")
        if direction == "followers"
        else (
            "follower_id",
            "followee_id",
        )
    )
    rows = (
        session.execute(
            text(f"""
                select a.id, a.username, a.display_name, a.avatar_url
                from follows f join profiles a on a.id = f.{other}
                where f.{me} = :u and f.status = 'accepted' and a.status = 'active'
                order by f.created_at desc
                limit :limit offset :offset
            """),
            {"u": user_id, "limit": limit, "offset": offset},
        )
        .mappings()
        .all()
    )
    total: int = session.execute(
        text(f"""
            select count(*) from follows f join profiles a on a.id = f.{other}
            where f.{me} = :u and f.status = 'accepted' and a.status = 'active'
        """),
        {"u": user_id},
    ).scalar_one()
    return rows, total


def can_view_content(session: Session, viewer_id: UUID, target_id: UUID) -> bool:
    """非公開アカウントのフォロワー一覧などを、見てよいか。"""
    sql = text("""
        select a.is_private = false or a.id = :v or exists (
            select 1 from follows f where f.follower_id = :v and f.followee_id = a.id
              and f.status = 'accepted'
        )
        from profiles a where a.id = :t
    """)
    return bool(session.execute(sql, {"v": viewer_id, "t": target_id}).scalar_one_or_none())


# ---------------------------------------------------------------- ブロック(7-4)


def insert_block(session: Session, blocker_id: UUID, blocked_id: UUID) -> None:
    """ブロックする。お互いのフォローも外す(ブロックした相手のタイムラインに出ないように)。"""
    session.execute(
        text("insert into blocks (blocker_id, blocked_id) values (:a, :b) on conflict do nothing"),
        {"a": blocker_id, "b": blocked_id},
    )
    session.execute(
        text("""
            delete from follows
            where (follower_id = :a and followee_id = :b) or (follower_id = :b and followee_id = :a)
        """),
        {"a": blocker_id, "b": blocked_id},
    )


def delete_block(session: Session, blocker_id: UUID, blocked_id: UUID) -> None:
    session.execute(
        text("delete from blocks where blocker_id = :a and blocked_id = :b"),
        {"a": blocker_id, "b": blocked_id},
    )


def list_blocks(session: Session, user_id: UUID) -> Sequence[RowMapping]:
    sql = text("""
        select a.id, a.username, a.display_name, a.avatar_url
        from blocks b join profiles a on a.id = b.blocked_id
        where b.blocker_id = :u order by b.created_at desc
    """)
    return session.execute(sql, {"u": user_id}).mappings().all()


def get_user_id_any(session: Session, username: str) -> UUID | None:
    """ブロック解除用:ブロック関係があっても id を引く。"""
    user_id: UUID | None = session.execute(
        text("select id from profiles where username = :u and status = 'active'"),
        {"u": username.lower()},
    ).scalar_one_or_none()
    return user_id


# ---------------------------------------------------------------- 退会・エクスポート(21-2・21-3)


def anonymize_and_delete_content(session: Session, user_id: UUID) -> list[str]:
    """退会:プロフィールを匿名化し、本人のデータを消す。ストレージから消すパスを返す。

    auth.users の削除(= 全データの物理削除)はワーカーが Supabase の管理 API で行う。
    それまでの間も、他の人からは見えないように status = 'deleted' にする。
    """
    params = {"id": user_id}
    paths = session.execute(
        text("select path, thumbnail_path from media where owner_id = :id"), params
    ).all()
    session.execute(
        text("""
            update profiles set
                status = 'deleted',
                username = 'deleted_' || substr(replace(id::text, '-', ''), 1, 12),
                display_name = '退会したユーザー', bio = '',
                avatar_url = null, avatar_media_id = null
            where id = :id
        """),
        params,
    )
    for statement in (
        "update posts set deleted_at = now() where user_id = :id and deleted_at is null",
        # 先に、いいねしていた投稿のカウンタを減らしてから、いいねを消す
        """update posts set like_count = greatest(like_count - 1, 0)
           where id in (select post_id from likes where user_id = :id)""",
        "delete from likes where user_id = :id",
        "delete from follows where follower_id = :id or followee_id = :id",
        "delete from push_subscriptions where user_id = :id",
        "delete from chat_messages where user_id = :id",
        "delete from media where owner_id = :id",
    ):
        session.execute(text(statement), params)
    return [p for row in paths for p in row if p]


def export_rows(session: Session, sql: str, user_id: UUID) -> list[dict[str, Any]]:
    return [dict(row) for row in session.execute(text(sql), {"id": user_id}).mappings().all()]

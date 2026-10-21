"""投稿・いいねの DB アクセス。SQL はここにだけ書く。

一覧の取り方(4-6 の N+1 対策):
    ① 投稿を1回の SQL で取る(作成者・自分がいいね済みかも JOIN / EXISTS で一緒に)
    ② 画像・ハッシュタグを「投稿 id のリスト」で1回ずつまとめて取る(where post_id = any(:ids))
    → 何件あっても SQL は3回。1件ずつ画像を取りに行くと 1 + N 回になる
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.core.visibility import can_view_content_of, post_is_alive
from app.posts.schemas import PostSort

# 一覧・詳細で共通の列。:viewer_id(閲覧者)が必要
_SELECT = f"""
    select
        p.id,
        p.content,
        p.image_url,
        p.created_at,
        p.updated_at,
        p.version,
        p.like_count,
        p.comment_count,
        p.comments_disabled,
        a.id           as author_id,
        a.username     as author_username,
        a.display_name as author_display_name,
        a.avatar_url   as author_avatar_url,
        am.path        as author_avatar_path,
        exists (
            select 1 from likes l where l.post_id = p.id and l.user_id = :viewer_id
        ) as liked_by_me
    from posts p
    join profiles a on a.id = p.user_id
    left join media am on am.id = a.avatar_media_id
    where {post_is_alive("p")} and {can_view_content_of("a")}
"""

# 並び順は辞書で決めた SQL だけを使う。利用者の入力を SQL に直接入れない(4-4・8-5)
_ORDER_BY: dict[str, str] = {
    "new": "p.created_at desc, p.id desc",
    "likes": "p.like_count desc, p.created_at desc, p.id desc",
}

# :cursor_t が null(1ページ目)なら条件なし。型が決まらないと PostgreSQL がエラーにするので cast する
_CURSOR_CONDITION = """
    and (
        cast(:cursor_t as timestamptz) is null
        or (p.created_at, p.id) < (cast(:cursor_t as timestamptz), cast(:cursor_id as bigint))
    )
"""


def _cursor_params(cursor: tuple[datetime, int] | None) -> dict[str, Any]:
    return {"cursor_t": cursor[0] if cursor else None, "cursor_id": cursor[1] if cursor else None}


# ---------------------------------------------------------------- 取得


def get_post(session: Session, post_id: int, viewer_id: UUID) -> RowMapping | None:
    """閲覧者が見てよい投稿を1件返す。"""
    sql = text(f"{_SELECT} and p.id = :post_id")
    return (
        session.execute(sql, {"post_id": post_id, "viewer_id": viewer_id}).mappings().one_or_none()
    )


def list_timeline(
    session: Session, viewer_id: UUID, cursor: tuple[datetime, int] | None, limit: int
) -> Sequence[RowMapping]:
    """全体のタイムライン(見てよい投稿すべて)。次ページの有無を知るため limit + 1 件取る。"""
    sql = text(f"""
        {_SELECT} {_CURSOR_CONDITION}
        order by p.created_at desc, p.id desc
        limit :limit
    """)
    params = {"viewer_id": viewer_id, "limit": limit + 1, **_cursor_params(cursor)}
    return session.execute(sql, params).mappings().all()


def list_feed(
    session: Session, viewer_id: UUID, cursor: tuple[datetime, int] | None, limit: int
) -> Sequence[RowMapping]:
    """フォロー中の人と自分の投稿(4-2)。"""
    sql = text(f"""
        {_SELECT}
        and (
            p.user_id = :viewer_id
            or exists (
                select 1 from follows f
                where f.follower_id = :viewer_id and f.followee_id = p.user_id
                  and f.status = 'accepted'
            )
        )
        {_CURSOR_CONDITION}
        order by p.created_at desc, p.id desc
        limit :limit
    """)
    params = {"viewer_id": viewer_id, "limit": limit + 1, **_cursor_params(cursor)}
    return session.execute(sql, params).mappings().all()


def list_user_posts(
    session: Session, viewer_id: UUID, author_id: UUID, sort: PostSort, limit: int, offset: int
) -> tuple[Sequence[RowMapping], int]:
    """ユーザーの投稿一覧と総件数(4-1)。"""
    params = {"viewer_id": viewer_id, "author_id": author_id, "limit": limit, "offset": offset}
    rows = (
        session.execute(
            text(f"""
                {_SELECT} and p.user_id = :author_id
                order by {_ORDER_BY[sort]}
                limit :limit offset :offset
            """),
            params,
        )
        .mappings()
        .all()
    )
    total = session.execute(
        text(f"""
            select count(*) from posts p join profiles a on a.id = p.user_id
            where {post_is_alive("p")} and {can_view_content_of("a")} and p.user_id = :author_id
        """),
        params,
    ).scalar_one()
    return rows, total


def list_hashtag_posts(
    session: Session, viewer_id: UUID, tag: str, cursor: tuple[datetime, int] | None, limit: int
) -> Sequence[RowMapping]:
    """ハッシュタグが付いた投稿(4-3)。"""
    sql = text(f"""
        {_SELECT}
        and exists (
            select 1 from post_hashtags ph join hashtags h on h.id = ph.hashtag_id
            where ph.post_id = p.id and h.name = :tag
        )
        {_CURSOR_CONDITION}
        order by p.created_at desc, p.id desc
        limit :limit
    """)
    params = {"viewer_id": viewer_id, "tag": tag, "limit": limit + 1, **_cursor_params(cursor)}
    return session.execute(sql, params).mappings().all()


def escape_like(value: str) -> str:
    """LIKE の特殊文字(% _ \\)を、ただの文字として扱うようにする。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_posts(
    session: Session, viewer_id: UUID, query: str, limit: int, offset: int
) -> Sequence[RowMapping]:
    """本文の部分一致検索(21-7)。pg_trgm の GIN インデックスが効く。

    検索語は必ずバインド変数(:pattern)で渡す。f-string で SQL に埋め込むと
    `' or 1=1 --` のような入力で SQL を書き換えられる(SQL インジェクション。8-5)。
    """
    sql = text(f"""
        {_SELECT} and p.content ilike :pattern escape '\\'
        order by p.created_at desc, p.id desc
        limit :limit offset :offset
    """)
    params = {
        "viewer_id": viewer_id,
        "pattern": f"%{escape_like(query)}%",
        "limit": limit,
        "offset": offset,
    }
    return session.execute(sql, params).mappings().all()


def list_popular_post_ids(session: Session, since: datetime, limit: int) -> list[int]:
    """最近の人気投稿の id(いいね数順)。公開アカウントだけなので、閲覧者によらず同じ結果になる。

    閲覧者によらないので、結果を Redis にキャッシュできる(13-1)。
    """
    sql = text(f"""
        select p.id from posts p join profiles a on a.id = p.user_id
        where {post_is_alive("p")} and a.status = 'active' and a.is_private = false
          and p.created_at >= :since
        order by p.like_count desc, p.id desc
        limit :limit
    """)
    return list(session.execute(sql, {"since": since, "limit": limit}).scalars().all())


def get_posts_by_ids(session: Session, viewer_id: UUID, ids: Sequence[int]) -> Sequence[RowMapping]:
    """id のリストで、見てよい投稿を取る(順番は呼び出し側で並べ直す)。"""
    sql = text(f"{_SELECT} and p.id = any(:ids)")
    return session.execute(sql, {"viewer_id": viewer_id, "ids": list(ids)}).mappings().all()


def get_media_for_posts(session: Session, post_ids: Sequence[int]) -> Sequence[RowMapping]:
    """複数の投稿の画像を、1回の SQL でまとめて取る(N+1 対策)。"""
    sql = text("""
        select pm.post_id, pm.position, m.id, m.path, m.thumbnail_path, m.width, m.height
        from post_media pm join media m on m.id = pm.media_id
        where pm.post_id = any(:ids) and m.status <> 'failed'
        order by pm.post_id, pm.position
    """)
    return session.execute(sql, {"ids": list(post_ids)}).mappings().all()


def get_hashtags_for_posts(session: Session, post_ids: Sequence[int]) -> Sequence[RowMapping]:
    sql = text("""
        select ph.post_id, h.name from post_hashtags ph join hashtags h on h.id = ph.hashtag_id
        where ph.post_id = any(:ids)
        order by h.name
    """)
    return session.execute(sql, {"ids": list(post_ids)}).mappings().all()


def get_post_owner(session: Session, post_id: int) -> RowMapping | None:
    """削除されていない投稿の作成者と状態(所有者チェック用)。"""
    sql = text("""
        select id, user_id, version, hidden_at, comments_disabled from posts
        where id = :id and deleted_at is null
    """)
    return session.execute(sql, {"id": post_id}).mappings().one_or_none()


# ---------------------------------------------------------------- 作成・更新・削除


def insert_post(session: Session, user_id: UUID, content: str) -> int:
    sql = text("insert into posts (user_id, content) values (:user_id, :content) returning id")
    post_id: int = session.execute(sql, {"user_id": user_id, "content": content}).scalar_one()
    return post_id


def insert_post_media(session: Session, post_id: int, media_ids: Sequence[UUID]) -> None:
    for position, media_id in enumerate(media_ids):
        session.execute(
            text("insert into post_media (post_id, media_id, position) values (:p, :m, :pos)"),
            {"p": post_id, "m": media_id, "pos": position},
        )


def replace_hashtags(session: Session, post_id: int, tags: Sequence[str]) -> None:
    """投稿のハッシュタグを付け直す(ない名前は hashtags に追加)。"""
    session.execute(text("delete from post_hashtags where post_id = :id"), {"id": post_id})
    if not tags:
        return
    session.execute(
        text(
            "insert into hashtags (name) select unnest(cast(:tags as text[])) "
            "on conflict (name) do nothing"
        ),
        {"tags": list(tags)},
    )
    session.execute(
        text("""
            insert into post_hashtags (post_id, hashtag_id)
            select :id, h.id from hashtags h where h.name = any(cast(:tags as text[]))
        """),
        {"id": post_id, "tags": list(tags)},
    )


def update_post(session: Session, post_id: int, version: int, values: dict[str, Any]) -> int | None:
    """楽観的ロックつきで更新する(10-2)。

    `where version = :version` で、読んだときから誰も更新していない場合だけ書き換える。
    0 件なら、その間に別の更新があった(= 競合)ので None を返す。
    """
    allowed = {"content", "comments_disabled"}
    sets = ", ".join(f"{column} = :{column}" for column in values if column in allowed)
    sql = text(f"""
        update posts set {sets}, version = version + 1
        where id = :id and version = :version and deleted_at is null
        returning version
    """)
    new_version: int | None = session.execute(
        sql, {"id": post_id, "version": version, **values}
    ).scalar_one_or_none()
    return new_version


def soft_delete_post(session: Session, post_id: int) -> list[str]:
    """投稿を論理削除し、関連データを片付ける(10-1)。消すべき画像のパスを返す。

    呼び出し元の1つのトランザクションの中で実行する。途中で失敗したら全部取り消される。
    """
    session.execute(
        text("update posts set deleted_at = now() where id = :id and deleted_at is null"),
        {"id": post_id},
    )
    session.execute(text("delete from likes where post_id = :id"), {"id": post_id})
    session.execute(text("update posts set like_count = 0 where id = :id"), {"id": post_id})
    session.execute(
        text("update comments set deleted_at = now() where post_id = :id and deleted_at is null"),
        {"id": post_id},
    )
    session.execute(text("delete from notifications where post_id = :id"), {"id": post_id})
    paths = session.execute(
        text("""
            delete from media m using post_media pm
            where pm.media_id = m.id and pm.post_id = :id
            returning m.path, m.thumbnail_path
        """),
        {"id": post_id},
    ).all()
    return [p for row in paths for p in row if p]


# ---------------------------------------------------------------- いいね


def insert_like(session: Session, user_id: UUID, post_id: int) -> int | None:
    """いいねを追加し、カウンタを +1 する。すでにいいね済みなら何もせず None。

    `like_count = like_count + 1` は DB の中で足し算するアトミックな更新(10-2)。
    アプリで「読む → +1 → 書く」とすると、同時に押されたときに1回分が消える。
    """
    inserted = session.execute(
        text("""
            insert into likes (user_id, post_id) values (:user_id, :post_id)
            on conflict do nothing returning post_id
        """),
        {"user_id": user_id, "post_id": post_id},
    ).one_or_none()
    if inserted is None:
        return None
    count: int = session.execute(
        text("update posts set like_count = like_count + 1 where id = :id returning like_count"),
        {"id": post_id},
    ).scalar_one()
    return count


def delete_like(session: Session, user_id: UUID, post_id: int) -> int | None:
    """いいねを取り消し、カウンタを -1 する。いいねしていなければ None。"""
    deleted = session.execute(
        text("delete from likes where user_id = :user_id and post_id = :post_id returning post_id"),
        {"user_id": user_id, "post_id": post_id},
    ).one_or_none()
    if deleted is None:
        return None
    count: int = session.execute(
        text("""
            update posts set like_count = greatest(like_count - 1, 0)
            where id = :id returning like_count
        """),
        {"id": post_id},
    ).scalar_one()
    return count


def get_like_count(session: Session, post_id: int) -> int:
    count: int = session.execute(
        text("select like_count from posts where id = :id"), {"id": post_id}
    ).scalar_one()
    return count


def is_liked(session: Session, user_id: UUID, post_id: int) -> bool:
    return bool(
        session.execute(
            text("select exists (select 1 from likes where user_id = :u and post_id = :p)"),
            {"u": user_id, "p": post_id},
        ).scalar_one()
    )


# ---------------------------------------------------------------- 通報


def insert_report(session: Session, reporter_id: UUID, post_id: int, reason: str) -> bool:
    """通報する。同じ人が同じ投稿を2回通報しても1件だけ(False を返す)。"""
    row = session.execute(
        text("""
            insert into reports (reporter_id, post_id, reason) values (:r, :p, :reason)
            on conflict (reporter_id, post_id) do nothing returning id
        """),
        {"r": reporter_id, "p": post_id, "reason": reason},
    ).one_or_none()
    return row is not None

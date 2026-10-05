from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_posts(session: Session, user_id: UUID, limit: int):
    """投稿の一覧を取得する。"""

    sql = text("""
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
          order by p.created_at desc, p.id desc
          limit :limit
          """)

    result = session.execute(sql, {"user_id": user_id, "limit": limit})

    return result.mappings().all()  # 列名で取り出せる行のリストにする

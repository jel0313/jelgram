from uuid import UUID

from app.core.db import Session
from app.posts import repository
from app.posts.constants import TIMELINE_LIMIT
from app.posts.schemas import Author, PostResponse


def get_timeline(session : Session, user_id : UUID) -> list[PostResponse]:
    """タイムラインの投稿を新しい順に返す。"""
    # 1. repository.get_posts() を呼び出して、投稿の一覧を取得する
    posts = repository.get_posts(session, user_id, TIMELINE_LIMIT)

    # 2. PostResponse のリストを入れる箱を作る
    result = []

    # 3. 行を 1 つずつ取り出して、繰り返す
    #  3-1. 行の author_ で始まる 3 列から Author を 1 つ作る
    #         author_id           → id
    #         author_display_name → display_name
    #         author_avatar_url   → avatar_url
    #  3-2. 行の残りの列と、3-1 の Author から PostResponse を 1 つ作る
    #         id, content, image_url, created_at はそのまま
    #         author には 3-1 で作ったもの
    #         like_count, liked_by_me はそのまま
    for post in posts:
        author = Author(
            id=post["author_id"],
            display_name=post["author_display_name"],
            avatar_url=post["author_avatar_url"],
        )

        post_response = PostResponse(
            id=post["id"],
            content=post["content"],
            image_url=post["image_url"],
            created_at=post["created_at"],
            author=author,
            like_count=post["like_count"],
            liked_by_me=post["liked_by_me"],
        )

        #  3-3. できた PostResponse を箱に追加する
        result.append(post_response)

    # 4. 箱を返す
    return result

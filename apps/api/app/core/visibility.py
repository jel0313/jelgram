"""「この人のコンテンツを、閲覧者が見てよいか」の SQL 条件(7-3・7-4)。

投稿・コメント・画像・検索など、複数の機能で同じルールを使うため、ここに1か所だけ書く。
どれも閲覧者の ID を `:viewer_id` というバインド変数で受け取る。

    見てよい = 相手が有効なアカウント
             かつ どちら向きにもブロックがない
             かつ(公開アカウント または 自分 または 承認済みのフォロワー)
"""


def not_blocked(author: str) -> str:
    """閲覧者と author の間に、どちら向きにもブロックがない。"""
    return f"""not exists (
        select 1 from blocks b
        where (b.blocker_id = {author}.id and b.blocked_id = :viewer_id)
           or (b.blocker_id = :viewer_id and b.blocked_id = {author}.id)
    )"""


def can_view_content_of(author: str) -> str:
    """閲覧者が author(profiles の別名)の投稿などを見てよい。"""
    return f"""(
        {author}.status = 'active'
        and {not_blocked(author)}
        and (
            {author}.is_private = false
            or {author}.id = :viewer_id
            or exists (
                select 1 from follows f
                where f.follower_id = :viewer_id and f.followee_id = {author}.id
                  and f.status = 'accepted'
            )
        )
    )"""


def post_is_alive(post: str) -> str:
    """削除されておらず、管理者に非表示にもされていない投稿。"""
    return f"({post}.deleted_at is null and {post}.hidden_at is null)"

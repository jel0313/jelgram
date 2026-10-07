"""投稿一覧のテスト(WBS 5.4)。開発用 DB を使い、データはロールバックで残さない。"""

from collections.abc import Callable
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.main import app

client = TestClient(app)


# 未認証ユーザーは投稿一覧にアクセスできない
def test_unauthenticated_user_cannot_access_posts():
    """トークンなしは 401。"""
    response = client.get("/posts")
    assert response.status_code == 401
    assert response.json() == {"detail": "認証が必要です"}


# insert_post はテスト用のヘルパー関数。DB に投稿を入れて、その id を返す。
def insert_post(session: Session, user_id: UUID, content: str) -> int:
    """テスト用の投稿を入れて、その id を返す。"""
    sql = text("insert into posts (user_id, content) values (:user_id, :content) returning id")
    return session.execute(sql, {"user_id": user_id, "content": content}).scalar_one()


# login_as はテスト用のヘルパー関数。指定したユーザーでログイン中にする。
def login_as(user_id: UUID) -> None:
    """このユーザーでログイン中にする(認証を差し替える)。"""
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)


# ログイン中に呼ぶと 200 で、入れた投稿が仕様の形で返る
def test_authenticated_user_can_access_posts(
    db_client: TestClient, db_session: Session, create_user: Callable[..., UUID]
) -> None:
    """ログイン中に呼ぶと 200 で、入れた投稿が仕様の形で返る。"""
    # 準備:DB にユーザーと投稿を入れ、そのユーザーでログイン中にする
    user_id = create_user("Aさん")
    post_id = insert_post(db_session, user_id, "テストの投稿")
    login_as(user_id)

    # 実行
    response = db_client.get("/posts")

    # 確認:自分が入れた投稿を id で探して、中身を仕様と比べる
    assert response.status_code == 200
    post = next(p for p in response.json() if p["id"] == post_id)
    assert post["content"] == "テストの投稿"
    assert post["image_url"] is None
    assert post["author"] == {"id": str(user_id), "display_name": "Aさん", "avatar_url": None}
    assert post["like_count"] == 0
    assert post["liked_by_me"] is False

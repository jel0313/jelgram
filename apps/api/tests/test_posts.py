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

# 関数:test_〜(引数なし) の形で書くと、pytest が自動でテストとして認識する。
#   1. client で GET /posts を呼ぶ
#   2. ステータスが 401 であることを assert
#   3. JSON が {"detail": "認証が必要です"} であることを assert
def test_unauthenticated_user_cannot_access_posts():
    """トークンなしは 401。"""
    response = client.get("/posts")
    assert response.status_code == 401
    assert response.json() == {"detail": "認証が必要です"}
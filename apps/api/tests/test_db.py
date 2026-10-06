"""DB 接続のテスト(WBS 5.3)。開発用 DB を使い、データはロールバックで残さない。"""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import engine


def test_can_connect(db_session: Session) -> None:
    """DB に接続して SQL を実行できる。"""
    assert db_session.execute(text("select 1")).scalar_one() == 1


def test_profile_is_created_by_trigger(
    db_session: Session, create_user: Callable[..., UUID]
) -> None:
    """auth.users に入れると、トリガーで profiles ができる(表示名もメタデータから入る)。"""
    user_id = create_user("Aさん")

    display_name = db_session.execute(
        text("select display_name from profiles where id = :id"), {"id": user_id}
    ).scalar_one()

    assert display_name == "Aさん"


def test_commit_does_not_reach_db(db_session: Session, create_user: Callable[..., UUID]) -> None:
    """テストの中で commit しても、本当には確定しない(別の接続からは見えない)。"""
    user_id = create_user()
    db_session.commit()

    with engine.connect() as other_connection:
        count = other_connection.execute(
            text("select count(*) from profiles where id = :id"), {"id": user_id}
        ).scalar_one()

    assert count == 0

"""IT:認可の横断テスト(7章・14-6)。

「他人の ID を指定しても、データが取れない・変えられない」ことを
API 経由で確かめる(IDOR 対策。7-6)。
"""

from collections.abc import Callable

import httpx2
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.fakes import make_image
from tests.integration.conftest import User

pytestmark = pytest.mark.anyio


async def create_post(client: httpx2.AsyncClient, user: User, content: str = "投稿") -> int:
    response = await client.post("/posts", json={"content": content}, headers=user.headers)
    assert response.status_code == 201, response.text
    post_id: int = response.json()["id"]
    return post_id


class TestOwnership:
    async def test_cannot_edit_or_delete_others_post(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User]
    ) -> None:
        """7-1:他人の投稿は 403。"""
        alice, mallory = create_user(), create_user()
        post_id = await create_post(client, alice)
        edit = await client.patch(
            f"/posts/{post_id}", json={"content": "改ざん", "version": 1}, headers=mallory.headers
        )
        assert edit.status_code == 403 and edit.json()["code"] == "not_post_owner"
        assert (
            await client.delete(f"/posts/{post_id}", headers=mallory.headers)
        ).status_code == 403
        assert (await client.get(f"/posts/{post_id}", headers=alice.headers)).json()[
            "content"
        ] == "投稿"

    async def test_comment_permissions(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
    ) -> None:
        """7-2:投稿者は他人のコメントを消せる。第三者は消せない。編集は書いた本人だけ。"""
        owner, commenter, other = create_user(), create_user(), create_user()
        post_id = await create_post(client, owner)
        c1 = (
            await client.post(
                f"/posts/{post_id}/comments", json={"content": "c1"}, headers=commenter.headers
            )
        ).json()
        c2 = (
            await client.post(
                f"/posts/{post_id}/comments", json={"content": "c2"}, headers=commenter.headers
            )
        ).json()

        assert (
            await client.delete(f"/comments/{c1['id']}", headers=other.headers)
        ).status_code == 403
        assert (
            await client.patch(
                f"/comments/{c1['id']}", json={"content": "x"}, headers=owner.headers
            )
        ).status_code == 403
        assert (
            await client.patch(
                f"/comments/{c1['id']}", json={"content": "編集"}, headers=commenter.headers
            )
        ).status_code == 200
        assert (
            await client.delete(f"/comments/{c1['id']}", headers=owner.headers)
        ).status_code == 204
        assert (
            await client.delete(f"/comments/{c2['id']}", headers=commenter.headers)
        ).status_code == 204

        post = (await client.get(f"/posts/{post_id}", headers=owner.headers)).json()
        assert post["comment_count"] == 0
        actions = db_session.execute(text("select action from audit_logs")).scalars().all()
        assert "comment.delete_by_post_owner" in actions

    async def test_notifications_and_chat_are_private(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
    ) -> None:
        """他人の通知を既読にできない・他人の会話履歴は読めない。"""
        alice, bob, mallory = create_user(), create_user(), create_user()
        post_id = await create_post(client, alice)
        await client.post(f"/posts/{post_id}/like", headers=bob.headers)
        note_id = db_session.execute(
            text("select id from notifications where recipient_id = :u"), {"u": alice.id}
        ).scalar_one()

        await client.post("/notifications/read", json={"ids": [note_id]}, headers=mallory.headers)
        assert (await client.get("/notifications/unread-count", headers=alice.headers)).json()[
            "unread"
        ] == 1

        await client.post(
            "/chat", json={"message": "秘密の相談", "session_id": "s1"}, headers=alice.headers
        )
        stolen = await client.get(
            "/chat/history", params={"session_id": "s1"}, headers=mallory.headers
        )
        assert stolen.json() == []


class TestPrivateAccount:
    async def test_follow_request_flow(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User]
    ) -> None:
        """7-3:非公開アカウントの投稿は、承認済みフォロワーだけが見られる。"""
        private, fan, stranger = create_user(private=True), create_user(), create_user()
        post_id = await create_post(client, private, "ないしょ")

        assert (await client.get(f"/posts/{post_id}", headers=stranger.headers)).status_code == 404
        listing = (
            await client.get(f"/users/{private.username}/posts", headers=stranger.headers)
        ).json()
        assert listing["total"] == 0
        profile = (await client.get(f"/users/{private.username}", headers=stranger.headers)).json()
        assert profile["is_private"] is True and profile["post_count"] == 1  # 件数は見える

        followed = await client.post(f"/users/{private.username}/follow", headers=fan.headers)
        assert followed.json() == {"follow_status": "pending"}
        assert (await client.get(f"/posts/{post_id}", headers=fan.headers)).status_code == 404

        requests = (await client.get("/me/follow-requests", headers=private.headers)).json()
        assert [r["user"]["id"] for r in requests] == [str(fan.id)]
        approved = await client.post(
            f"/me/follow-requests/{fan.id}/approve", headers=private.headers
        )
        assert approved.status_code == 204
        assert (await client.get(f"/posts/{post_id}", headers=fan.headers)).status_code == 200
        # 2回目の承認は 404(処理済み)
        assert (
            await client.post(f"/me/follow-requests/{fan.id}/approve", headers=private.headers)
        ).status_code == 404
        # 他人宛てのリクエストは承認できない
        assert (
            await client.post(f"/me/follow-requests/{fan.id}/approve", headers=stranger.headers)
        ).status_code == 404

    async def test_private_media_is_protected(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User]
    ) -> None:
        """9-6:非公開アカウントの画像は、フォロワー以外は取得できない。"""
        private, stranger = create_user(private=True), create_user()
        uploaded = await client.post(
            "/media", headers=private.headers, files={"file": ("a.png", make_image(), "image/png")}
        )
        media_id = uploaded.json()["id"]
        await client.post(
            "/posts", json={"content": "写真", "media_ids": [media_id]}, headers=private.headers
        )

        assert (await client.get(f"/media/{media_id}", headers=private.headers)).status_code == 200
        assert (await client.get(f"/media/{media_id}", headers=stranger.headers)).status_code == 404

    async def test_unprivate_accepts_pending(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User]
    ) -> None:
        private, fan = create_user(private=True), create_user()
        await client.post(f"/users/{private.username}/follow", headers=fan.headers)
        await client.patch("/me/profile", json={"is_private": False}, headers=private.headers)
        profile = (await client.get(f"/users/{private.username}", headers=fan.headers)).json()
        assert profile["follow_status"] == "following"


class TestBlock:
    async def test_block_hides_everything(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User]
    ) -> None:
        """7-4:ブロックした相手から見えない・操作できない(どちら向きでも)。"""
        alice, troll = create_user(), create_user()
        post_id = await create_post(client, alice)
        await client.post(f"/users/{alice.username}/follow", headers=troll.headers)

        assert (
            await client.post(f"/users/{troll.username}/block", headers=alice.headers)
        ).status_code == 204

        assert (await client.get(f"/posts/{post_id}", headers=troll.headers)).status_code == 404
        assert (
            await client.post(f"/posts/{post_id}/like", headers=troll.headers)
        ).status_code == 404
        assert (
            await client.post(
                f"/posts/{post_id}/comments", json={"content": "x"}, headers=troll.headers
            )
        ).status_code == 404
        assert (
            await client.get(f"/users/{alice.username}", headers=troll.headers)
        ).status_code == 404
        timeline = (await client.get("/posts", headers=troll.headers)).json()
        assert all(p["id"] != post_id for p in timeline["items"])
        # フォローも外れている
        followers = (
            await client.get(f"/users/{alice.username}/followers", headers=alice.headers)
        ).json()
        assert followers["total"] == 0
        # ブロックした側からも相手が見えない
        assert (
            await client.get(f"/users/{troll.username}", headers=alice.headers)
        ).status_code == 404
        blocks = (await client.get("/me/blocks", headers=alice.headers)).json()
        assert [b["id"] for b in blocks] == [str(troll.id)]

        assert (
            await client.delete(f"/users/{troll.username}/block", headers=alice.headers)
        ).status_code == 204
        assert (await client.get(f"/posts/{post_id}", headers=troll.headers)).status_code == 200


class TestAdmin:
    async def test_user_cannot_use_admin_api(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User]
    ) -> None:
        user = create_user()
        assert (await client.get("/admin/reports", headers=user.headers)).status_code == 403

    async def test_report_and_resolve(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User]
    ) -> None:
        """7-5:通報 → 管理者が非表示 → 誰からも見えない。監査ログが残る。"""
        author, reporter, admin = create_user(), create_user(), create_user(role="admin")
        post_id = await create_post(client, author)
        await client.post(
            f"/posts/{post_id}/report", json={"reason": "スパム"}, headers=reporter.headers
        )

        reports = (await client.get("/admin/reports", headers=admin.headers)).json()
        assert [(r["post_id"], r["reason"]) for r in reports] == [(post_id, "スパム")]
        resolved = await client.post(
            f"/admin/reports/{reports[0]['id']}/resolve",
            json={"action": "hide_post"},
            headers=admin.headers,
        )
        assert resolved.status_code == 204
        again = await client.post(
            f"/admin/reports/{reports[0]['id']}/resolve",
            json={"action": "dismiss"},
            headers=admin.headers,
        )
        assert again.status_code == 409  # 処理済み

        assert (await client.get(f"/posts/{post_id}", headers=reporter.headers)).status_code == 404
        logs = (await client.get("/admin/audit-logs", headers=admin.headers)).json()
        assert logs[0]["action"] == "report.hide_post" and logs[0]["actor_id"] == str(admin.id)

    async def test_suspend(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User]
    ) -> None:
        """凍結したユーザーは API を使えず、投稿も見えなくなる。管理者は凍結できない。"""
        user, viewer, admin = create_user(), create_user(), create_user(role="admin")
        post_id = await create_post(client, user)

        assert (
            await client.post(f"/admin/users/{user.id}/suspend", headers=admin.headers)
        ).status_code == 204
        me = await client.get("/me", headers=user.headers)
        assert me.status_code == 403 and me.json()["code"] == "account_suspended"
        assert (await client.get(f"/posts/{post_id}", headers=viewer.headers)).status_code == 404
        assert (
            await client.post(f"/admin/users/{admin.id}/suspend", headers=admin.headers)
        ).status_code == 404

        await client.post(f"/admin/users/{user.id}/unsuspend", headers=admin.headers)
        assert (await client.get("/me", headers=user.headers)).status_code == 200


async def test_logout_revokes_token(
    client: httpx2.AsyncClient, create_user: Callable[..., User]
) -> None:
    """6-5:ログアウト後は同じトークンが使えない。"""
    user = create_user()
    assert (await client.post("/auth/logout", headers=user.headers)).status_code == 204
    response = await client.get("/me", headers=user.headers)
    assert (
        response.status_code == 401 and response.json()["message"] == "ログアウト済みのトークンです"
    )

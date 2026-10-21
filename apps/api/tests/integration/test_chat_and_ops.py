"""IT:AI チャット・ワーカー(Outbox)・Webhook・退会・ヘルスチェック。"""

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.worker import handlers
from tests.fakes import FakeAI, FakePush, FakeStorage, make_image
from tests.integration.conftest import User

pytestmark = pytest.mark.anyio


class TestChat:
    async def test_conversation_is_saved_and_isolated_by_session(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], fake_ai: FakeAI
    ) -> None:
        user = create_user()
        first = await client.post(
            "/chat", json={"message": "やあ", "session_id": "s1"}, headers=user.headers
        )
        assert first.status_code == 200
        assert first.json()["reply"]["content"] == fake_ai.reply
        await client.post(
            "/chat", json={"message": "続き", "session_id": "s1"}, headers=user.headers
        )
        await client.post(
            "/chat", json={"message": "別の話", "session_id": "s2"}, headers=user.headers
        )

        history = (
            await client.get("/chat/history", params={"session_id": "s1"}, headers=user.headers)
        ).json()
        assert [(m["role"], m["content"]) for m in history] == [
            ("user", "やあ"),
            ("assistant", fake_ai.reply),
            ("user", "続き"),
            ("assistant", fake_ai.reply),
        ]
        # 2回目の呼び出しでは、前の会話も AI に渡している(s2 の会話は混ざらない)
        assert [m.text for m in fake_ai.calls[1][1]] == ["やあ", fake_ai.reply, "続き"]
        assert [m.text for m in fake_ai.calls[2][1]] == ["別の話"]

        sessions = (await client.get("/chat/sessions", headers=user.headers)).json()
        assert {s["session_id"] for s in sessions} == {"s1", "s2"}
        usage = (await client.get("/chat/usage", headers=user.headers)).json()
        assert usage["used_today"] == 3 and usage["prompt_tokens_today"] == 30

    async def test_about_post(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], fake_ai: FakeAI
    ) -> None:
        user = create_user("花子")
        post = (
            await client.post("/posts", json={"content": "猫かわいい"}, headers=user.headers)
        ).json()
        await client.post(
            "/chat",
            json={"message": "どう?", "session_id": "s", "post_id": post["id"]},
            headers=user.headers,
        )
        assert '<post author="花子">\n猫かわいい\n</post>' in fake_ai.calls[0][1][-1].text
        missing = await client.post(
            "/chat",
            json={"message": "?", "session_id": "s", "post_id": 999999},
            headers=user.headers,
        )
        assert missing.status_code == 404

    async def test_rate_limit_in_character(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], it_app: FastAPI
    ) -> None:
        """上限を超えると 429 と、キャラクターの口調のメッセージ。"""
        it_app.dependency_overrides[get_settings] = lambda: Settings(
            rate_limit_per_user_per_minute=2
        )  # type: ignore[call-arg]
        user = create_user()
        codes = []
        for i in range(3):
            r = await client.post(
                "/chat", json={"message": f"{i}", "session_id": "s"}, headers=user.headers
            )
            codes.append(r.status_code)
        assert codes == [200, 200, 429]
        assert "話しかけすぎ" in r.json()["message"] and r.headers["Retry-After"] == "60"

    async def test_ai_down_returns_503_in_character(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], fake_ai: FakeAI
    ) -> None:
        """12-7:AI が落ちていたら 503 と、キャラクターの口調の案内。"""
        fake_ai.fail = True
        r = await client.post(
            "/chat", json={"message": "hi", "session_id": "s"}, headers=create_user().headers
        )
        assert r.status_code == 503 and r.json()["code"] == "ai_unavailable"

    async def test_stream(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], fake_ai: FakeAI
    ) -> None:
        """12-3:SSE で delta が順に届き、最後に done。応答は保存される。"""
        user = create_user()
        response = await client.post(
            "/chat/stream", json={"message": "hi", "session_id": "s"}, headers=user.headers
        )
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            (block.split("\n")[0].removeprefix("event: "), json.loads(block.split("data: ", 1)[1]))
            for block in response.text.strip().split("\n\n")
            if block.startswith("event:")
        ]
        assert [e for e, _ in events] == ["delta", "delta", "done"]
        assert "".join(d["text"] for e, d in events if e == "delta") == fake_ai.reply
        history = (
            await client.get("/chat/history", params={"session_id": "s"}, headers=user.headers)
        ).json()
        assert history[-1]["content"] == fake_ai.reply

    async def test_stream_rate_limit_is_plain_http_error(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], it_app: FastAPI
    ) -> None:
        """ストリーミングでも、開始前のチェックは普通の 429 で返る。"""
        it_app.dependency_overrides[get_settings] = lambda: Settings(
            rate_limit_per_user_per_minute=1
        )  # type: ignore[call-arg]
        user = create_user()
        await client.post(
            "/chat/stream", json={"message": "1", "session_id": "s"}, headers=user.headers
        )
        second = await client.post(
            "/chat/stream", json={"message": "2", "session_id": "s"}, headers=user.headers
        )
        assert second.status_code == 429


class TestOutboxRelay:
    async def test_events_are_processed(
        self,
        client: httpx2.AsyncClient,
        create_user: Callable[..., User],
        db_session: Session,
        fake_storage: FakeStorage,
    ) -> None:
        """20-4:API が積んだイベント(画像の加工・AI 判定・プッシュ通知)をワーカーが処理する。"""
        alice, bob = create_user(), create_user()
        media = (
            await client.post(
                "/media",
                headers=alice.headers,
                files={"file": ("a.jpg", make_image("JPEG", (800, 600)), "image/jpeg")},
            )
        ).json()
        post = (
            await client.post(
                "/posts",
                json={"content": "脅迫する文", "media_ids": [media["id"]]},
                headers=alice.headers,
            )
        ).json()
        await client.post(
            "/me/push-subscriptions",
            json={"endpoint": "https://push.test/a", "keys": {"p256dh": "AAA", "auth": "BBB"}},
            headers=alice.headers,
        )
        await client.post(f"/posts/{post['id']}/like", headers=bob.headers)

        push = FakePush()
        ai = FakeAI(reply='{"flagged": true, "reason": "脅迫"}')
        dispatch = handlers.make_dispatcher(
            db_session, storage=fake_storage, ai=ai, push=push, settings=get_settings()
        )
        processed = handlers.relay_outbox(db_session, dispatch)

        assert processed == 3  # media.process・post.moderate・notification.created
        status = db_session.execute(
            text("select status, thumbnail_path from media where id = :id"), {"id": media["id"]}
        ).one()
        assert status[0] == "ready" and status[1] in fake_storage.objects
        assert push.sent[0]["body"].endswith("いいねしました")
        hidden = db_session.execute(
            text("select hidden_at is not null from posts where id = :id"), {"id": post["id"]}
        ).scalar_one()
        assert hidden is True
        assert handlers.relay_outbox(db_session, dispatch) == 0  # 2回目は何もしない

    async def test_failed_event_is_retried_later(self, db_session: Session) -> None:
        db_session.execute(
            text("insert into outbox_events (event_type, payload) values ('nope', '{}')")
        )

        def dispatch(event_type: str, payload: dict) -> None:  # type: ignore[type-arg]
            raise RuntimeError("失敗")

        handlers.relay_outbox(db_session, dispatch)
        row = db_session.execute(
            text(
                "select attempts, last_error, processed_at from outbox_events "
                "where event_type = 'nope'"
            )
        ).one()
        assert row[0] == 1 and "失敗" in row[1] and row[2] is None


class TestWebhook:
    def signed(
        self,
        body: dict,
        secret: str = "test-webhook-secret",  # noqa: S107
    ) -> tuple[bytes, dict[str, str]]:  # type: ignore[type-arg]
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))
        signature = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
        return raw, {
            "X-Webhook-Timestamp": ts,
            "X-Webhook-Signature": signature,
            "Content-Type": "application/json",
        }

    async def test_hides_post_once(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
    ) -> None:
        user = create_user()
        post_id = (await client.post("/posts", json={"content": "x"}, headers=user.headers)).json()[
            "id"
        ]
        raw, headers = self.signed(
            {"event_id": "ev-1", "type": "post.flagged", "post_id": post_id, "reason": "spam"}
        )

        first = await client.post("/webhooks/moderation", content=raw, headers=headers)
        second = await client.post("/webhooks/moderation", content=raw, headers=headers)

        assert first.json() == {"status": "processed"} and second.json() == {"status": "duplicate"}
        reports = db_session.execute(
            text("select count(*) from reports where post_id = :p"), {"p": post_id}
        ).scalar_one()
        assert reports == 1

    async def test_bad_signature(self, client: httpx2.AsyncClient) -> None:
        raw, headers = self.signed(
            {"event_id": "e", "type": "post.flagged", "post_id": 1, "reason": ""}, secret="wrong"
        )
        assert (
            await client.post("/webhooks/moderation", content=raw, headers=headers)
        ).status_code == 401


class TestAccount:
    async def test_export_and_delete(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
    ) -> None:
        """21-2・21-3:エクスポートで自分のデータが取れる。

        退会すると匿名化され、Outbox に削除が入る。
        """
        alice, bob = create_user(), create_user()
        post_id = (
            await client.post("/posts", json={"content": "わたしの投稿"}, headers=alice.headers)
        ).json()["id"]
        await client.post(f"/posts/{post_id}/like", headers=alice.headers)
        await client.post(f"/users/{bob.username}/follow", headers=alice.headers)

        export = (await client.get("/me/export", headers=alice.headers)).json()
        assert export["profile"]["username"] == alice.username
        assert [p["content"] for p in export["posts"]] == ["わたしの投稿"]
        assert len(export["likes"]) == 1 and export["following"][0]["username"] == bob.username

        assert (await client.delete("/me", headers=alice.headers)).status_code == 204
        assert (await client.get("/me", headers=alice.headers)).status_code == 401
        assert (
            await client.get(f"/users/{alice.username}", headers=bob.headers)
        ).status_code == 404
        profile = db_session.execute(
            text("select display_name, status from profiles where id = :id"), {"id": alice.id}
        ).one()
        assert tuple(profile) == ("退会したユーザー", "deleted")
        events = (
            db_session.execute(text("select event_type from outbox_events order by id"))
            .scalars()
            .all()
        )
        assert events[-1] == "user.purge"


class TestStories:
    async def test_expire(
        self, client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
    ) -> None:
        """11-5:24時間を過ぎたストーリーは見えなくなり、定期ジョブで消える。"""
        from app.stories.service import expire_stories

        user, follower = create_user(), create_user()
        await client.post(f"/users/{user.username}/follow", headers=follower.headers)
        media = (
            await client.post(
                "/media", headers=user.headers, files={"file": ("a.png", make_image(), "image/png")}
            )
        ).json()
        story = await client.post("/stories", json={"media_id": media["id"]}, headers=user.headers)
        assert story.status_code == 201
        assert len((await client.get("/stories", headers=follower.headers)).json()) == 1

        assert expire_stories(db_session, datetime.now(UTC) + timedelta(hours=25)) == 1
        assert (await client.get("/stories", headers=follower.headers)).json() == []


class TestHealth:
    async def test_health_checks_db_and_redis(self, it_app: FastAPI) -> None:
        transport = httpx2.ASGITransport(app=it_app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as c:
            assert (await c.get("/health")).json() == {
                "status": "ok",
                "checks": {"db": "ok", "redis": "ok"},
            }
            assert (await c.get("/health/live")).json() == {"status": "ok"}
            metrics = await c.get("/metrics")
            assert "http_requests_total" in metrics.text
            assert metrics.headers["X-Content-Type-Options"] == "nosniff"

    async def test_health_reports_redis_down(self, it_app: FastAPI) -> None:
        from app.core.redis import create_redis

        it_app.state.redis = create_redis("redis://127.0.0.1:1/0")
        transport = httpx2.ASGITransport(app=it_app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get("/health")
        assert response.status_code == 503 and response.json()["checks"]["redis"] == "error"

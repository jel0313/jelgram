"""IT:投稿まわりのシナリオ(登録 → 画像 → 投稿 → いいね → 通知 → コメント → 編集 → 削除)。"""

from collections.abc import Callable

import httpx2
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.fakes import FakeStorage, make_image
from tests.integration.conftest import User

pytestmark = pytest.mark.anyio


async def upload(client: httpx2.AsyncClient, user: User, fmt: str = "PNG") -> str:
    ext = {"PNG": "png", "JPEG": "jpg"}[fmt]
    response = await client.post(
        "/media",
        headers=user.headers,
        files={"file": (f"photo.{ext}", make_image(fmt), f"image/{ext.replace('jpg', 'jpeg')}")},
    )
    assert response.status_code == 201, response.text
    media_id: str = response.json()["id"]
    return media_id


async def test_post_lifecycle(
    client: httpx2.AsyncClient,
    create_user: Callable[..., User],
    db_session: Session,
    fake_storage: FakeStorage,
) -> None:
    alice = create_user("アリス")
    bob = create_user("ボブ")

    # ① 自分の情報(メールは本人にだけ返る)
    me = (await client.get("/me", headers=alice.headers)).json()
    assert me["username"] == alice.username and me["email"].endswith("@example.com")

    # ② 画像を2枚上げて、カルーセルで投稿する(冪等性キー付き)
    media = [await upload(client, alice), await upload(client, alice, "JPEG")]
    body = {"content": "初投稿 #テスト #Jelgram", "media_ids": media}
    headers = {**alice.headers, "Idempotency-Key": "key-1"}
    first = await client.post("/posts", json=body, headers=headers)
    assert first.status_code == 201, first.text
    post = first.json()
    assert [m["id"] for m in post["media"]] == media
    assert post["media"][0]["url"].startswith("https://storage.test/")
    assert post["hashtags"] == ["jelgram", "テスト"]

    # ③ 二度押し:同じキーなら同じ投稿が返り、2件目はできない(10-4)
    second = await client.post("/posts", json=body, headers=headers)
    assert second.json()["id"] == post["id"]
    count = db_session.execute(
        text("select count(*) from posts where user_id = :u"), {"u": alice.id}
    ).scalar_one()
    assert count == 1
    reused = await client.post("/posts", json={"content": "別の内容"}, headers=headers)
    assert reused.status_code == 422 and reused.json()["code"] == "idempotency_key_reused"

    # ④ 使用済みの画像は、別の投稿に付けられない
    again = await client.post(
        "/posts", json={"content": "x", "media_ids": media[:1]}, headers=alice.headers
    )
    assert again.status_code == 400 and again.json()["code"] == "media_not_usable"

    # ⑤ ボブがタイムラインで見て、いいねする → アリスに通知
    timeline = (await client.get("/posts", headers=bob.headers)).json()
    assert any(p["id"] == post["id"] for p in timeline["items"])
    liked = await client.post(f"/posts/{post['id']}/like", headers=bob.headers)
    assert liked.json() == {"post_id": post["id"], "like_count": 1, "liked_by_me": True}
    twice = await client.post(f"/posts/{post['id']}/like", headers=bob.headers)
    assert twice.json()["like_count"] == 1  # 2回押しても数はずれない

    notes = (await client.get("/notifications", headers=alice.headers)).json()
    assert [(n["type"], n["actor"]["id"]) for n in notes["items"]] == [("like", str(bob.id))]
    assert (await client.get("/notifications/unread-count", headers=alice.headers)).json() == {
        "unread": 1
    }
    await client.post("/notifications/read", json={}, headers=alice.headers)
    assert (await client.get("/notifications/unread-count", headers=alice.headers)).json() == {
        "unread": 0
    }

    # ⑥ コメント
    comment = await client.post(
        f"/posts/{post['id']}/comments", json={"content": "いいね!"}, headers=bob.headers
    )
    assert comment.status_code == 201
    comments = (await client.get(f"/posts/{post['id']}/comments", headers=alice.headers)).json()
    assert (
        comments["items"][0]["content"] == "いいね!" and comments["items"][0]["can_delete"] is True
    )
    detail = (await client.get(f"/posts/{post['id']}", headers=bob.headers)).json()
    assert (detail["like_count"], detail["comment_count"], detail["liked_by_me"]) == (1, 1, True)

    # ⑦ 編集(PATCH)→ version が上がる。古い version では 409(楽観的ロック)
    patched = await client.patch(
        f"/posts/{post['id']}",
        json={"content": "編集した #新タグ", "version": 1},
        headers=alice.headers,
    )
    assert patched.status_code == 200 and patched.json()["version"] == 2
    assert patched.json()["hashtags"] == ["新タグ"]
    stale = await client.patch(
        f"/posts/{post['id']}",
        json={"comments_disabled": True, "version": 1},
        headers=alice.headers,
    )
    assert stale.status_code == 409 and stale.json()["code"] == "post_version_conflict"

    # ⑧ PUT は全項目が必要
    put = await client.put(
        f"/posts/{post['id']}",
        json={"content": "全部置き換え", "comments_disabled": True, "version": 2},
        headers=alice.headers,
    )
    assert put.status_code == 200 and put.json()["comments_disabled"] is True
    blocked = await client.post(
        f"/posts/{post['id']}/comments", json={"content": "書けない"}, headers=bob.headers
    )
    assert blocked.status_code == 403 and blocked.json()["code"] == "comments_disabled"

    # ⑨ 削除:204 → 見えなくなる。いいね・画像の行も片付き、ファイル削除は Outbox に入る(10-1)
    deleted = await client.delete(f"/posts/{post['id']}", headers=alice.headers)
    assert deleted.status_code == 204
    assert (await client.get(f"/posts/{post['id']}", headers=bob.headers)).status_code == 404
    leftovers = db_session.execute(
        text("""
            select (select count(*) from likes where post_id = :p),
                   (select count(*) from post_media where post_id = :p),
                   (select count(*) from comments where post_id = :p and deleted_at is null),
                   (select count(*) from outbox_events
                    where event_type = 'media.delete' and processed_at is null)
        """),
        {"p": post["id"]},
    ).one()
    assert tuple(leftovers) == (0, 0, 0, 1)
    audit = (
        db_session.execute(
            text("select action from audit_logs where target_id = :p"), {"p": str(post["id"])}
        )
        .scalars()
        .all()
    )
    assert audit == ["post.delete"]


async def test_upload_validation(
    client: httpx2.AsyncClient, create_user: Callable[..., User]
) -> None:
    alice = create_user()
    fake_pdf = await client.post(
        "/media",
        headers=alice.headers,
        files={"file": ("a.png", b"%PDF-1.7 not image", "image/png")},
    )
    assert fake_pdf.status_code == 415
    too_big = await client.post(
        "/media",
        headers=alice.headers,
        files={"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * (7 * 1024 * 1024), "image/png")},
    )
    assert too_big.status_code == 413


async def test_direct_upload_flow(
    client: httpx2.AsyncClient, create_user: Callable[..., User], fake_storage: FakeStorage
) -> None:
    """署名付き URL で直接アップロード → complete で中身を検証(9-7)。"""
    alice = create_user()
    issued = await client.post(
        "/media/upload-url",
        json={"content_type": "image/png", "size_bytes": 1000},
        headers=alice.headers,
    )
    assert issued.status_code == 201
    media_id = issued.json()["media_id"]
    path = issued.json()["upload_url"].split("/upload/")[1].split("?")[0]

    # ブラウザがストレージに直接 PUT した、という状態を作る(中身は偽物)
    fake_storage.objects[path] = (b"not an image", "image/png")
    bad = await client.post(f"/media/{media_id}/complete", headers=alice.headers)
    assert bad.status_code == 415 and path not in fake_storage.objects

    issued = await client.post(
        "/media/upload-url",
        json={"content_type": "image/png", "size_bytes": 1000},
        headers=alice.headers,
    )
    media_id = issued.json()["media_id"]
    path = issued.json()["upload_url"].split("/upload/")[1].split("?")[0]
    fake_storage.objects[path] = (make_image("PNG"), "image/png")
    good = await client.post(f"/media/{media_id}/complete", headers=alice.headers)
    assert good.status_code == 200 and good.json()["width"] == 40


async def test_validation_errors(
    client: httpx2.AsyncClient, create_user: Callable[..., User]
) -> None:
    alice = create_user()
    response = await client.post("/posts", json={"content": "a" * 501}, headers=alice.headers)
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "body.content"
    assert (
        await client.post("/posts", json={"content": "死ね"}, headers=alice.headers)
    ).status_code == 400


async def test_rate_limit_on_posts(
    client: httpx2.AsyncClient, create_user: Callable[..., User]
) -> None:
    """投稿の連打は Redis のレート制限で 429(8-3)。"""
    from app.core.config import get_settings

    alice = create_user()
    limit = get_settings().rate_limit_posts_per_minute
    codes = [
        (await client.post("/posts", json={"content": f"{i}"}, headers=alice.headers)).status_code
        for i in range(limit + 1)
    ]
    assert codes.count(201) == limit and codes[-1] == 429

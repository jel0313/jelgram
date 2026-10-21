"""IT:フィード・ページング・検索・並び順・プロフィール(4章・13章)。"""

from collections.abc import Callable

import httpx2
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.integration.conftest import User

pytestmark = pytest.mark.anyio


def insert_posts(db_session: Session, user: User, contents: list[str]) -> list[int]:
    """レート制限を避けるため、テストデータは DB に直接入れる(作成日時を1秒ずつずらす)。"""
    ids = []
    for i, content in enumerate(contents):
        ids.append(
            db_session.execute(
                text("""
                    insert into posts (user_id, content, created_at)
                    values (:u, :c, now() - make_interval(secs => :i)) returning id
                """),
                {"u": user.id, "c": content, "i": len(contents) - i},
            ).scalar_one()
        )
    return ids


async def test_feed_cursor_pagination(
    client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
) -> None:
    """4-2:フォロー中 + 自分の投稿だけが、新しい順に、重複・抜けなく取れる。"""
    me, friend, stranger = create_user(), create_user(), create_user()
    mine = insert_posts(db_session, me, ["m1", "m2"])
    theirs = insert_posts(db_session, friend, ["f1", "f2", "f3"])
    insert_posts(db_session, stranger, ["s1"])
    await client.post(f"/users/{friend.username}/follow", headers=me.headers)

    seen: list[int] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = (await client.get("/feed", params=params, headers=me.headers)).json()
        seen += [p["id"] for p in page["items"]]
        pages += 1
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert sorted(seen) == sorted(mine + theirs)
    assert len(seen) == len(set(seen)) == 5 and pages == 3
    assert (
        await client.get("/feed", params={"cursor": "broken"}, headers=me.headers)
    ).status_code == 400


async def test_user_posts_offset_and_sort(
    client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
) -> None:
    """4-1・4-4:総件数つきのページングと、いいね数順。許可していない並び順は 422。"""
    author, viewer = create_user(), create_user()
    ids = insert_posts(db_session, author, ["a", "b", "c"])
    db_session.execute(text("update posts set like_count = 10 where id = :id"), {"id": ids[0]})

    page = (
        await client.get(
            f"/users/{author.username}/posts",
            params={"limit": 2, "offset": 2},
            headers=viewer.headers,
        )
    ).json()
    assert (page["total"], page["limit"], page["offset"], len(page["items"])) == (3, 2, 2, 1)

    by_likes = (
        await client.get(
            f"/users/{author.username}/posts", params={"sort": "likes"}, headers=viewer.headers
        )
    ).json()
    assert by_likes["items"][0]["id"] == ids[0]
    bad = await client.get(
        f"/users/{author.username}/posts",
        params={"sort": "id; drop table posts"},
        headers=viewer.headers,
    )
    assert bad.status_code == 422


async def test_search_treats_wildcards_literally(
    client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
) -> None:
    """8-5・21-7:検索語の % や ' は、ただの文字として扱う(SQL インジェクションにならない)。"""
    author, viewer = create_user(), create_user()
    insert_posts(db_session, author, ["セール 100%オフ", "100円", "it's ok"])

    async def search(q: str) -> list[str]:
        response = await client.get("/posts/search", params={"q": q}, headers=viewer.headers)
        assert response.status_code == 200
        return [p["content"] for p in response.json()]

    assert await search("100%") == ["セール 100%オフ"]
    assert await search("%") == ["セール 100%オフ"]
    assert await search("it's") == ["it's ok"]
    assert await search("' or 1=1 --") == []


async def test_hashtag_and_user_search(
    client: httpx2.AsyncClient, create_user: Callable[..., User]
) -> None:
    alice = create_user("Alice Wonder", username="alice_w")
    await client.post("/posts", json={"content": "#ラーメン 最高"}, headers=alice.headers)
    tagged = (await client.get("/hashtags/%23ラーメン/posts", headers=alice.headers)).json()
    assert len(tagged["items"]) == 1

    users = (await client.get("/users/search", params={"q": "ALICE"}, headers=alice.headers)).json()
    assert users[0]["username"] == "alice_w"
    assert (
        await client.get("/users/search", params={"q": "wonder"}, headers=alice.headers)
    ).json()[0]["id"] == str(alice.id)


async def test_profile_cache_is_invalidated(
    client: httpx2.AsyncClient, create_user: Callable[..., User], redis
) -> None:
    """13-2:プロフィールを変えたら、キャッシュが消えて新しい値が返る。"""
    alice, bob = create_user(), create_user()
    first = (await client.get(f"/users/{alice.username}", headers=bob.headers)).json()
    assert first["follower_count"] == 0
    assert redis.exists(f"cache:profile:v1:{alice.id}")

    await client.post(f"/users/{alice.username}/follow", headers=bob.headers)
    await client.patch("/me/profile", json={"bio": "はじめまして"}, headers=alice.headers)
    second = (await client.get(f"/users/{alice.username}", headers=bob.headers)).json()
    assert (second["follower_count"], second["bio"], second["follow_status"]) == (
        1,
        "はじめまして",
        "following",
    )


async def test_username_conflict(
    client: httpx2.AsyncClient, create_user: Callable[..., User]
) -> None:
    """2-5:ユーザー名の重複は 409(DB の一意制約で判定)。"""
    alice, bob = create_user(username="taken_name"), create_user()
    response = await client.patch(
        "/me/profile", json={"username": "TAKEN_NAME"}, headers=bob.headers
    )
    assert response.status_code == 409 and response.json()["code"] == "username_taken"
    assert alice.username == "taken_name"


async def test_popular_posts(
    client: httpx2.AsyncClient, create_user: Callable[..., User], db_session: Session
) -> None:
    author, private, viewer = create_user(), create_user(private=True), create_user()
    ids = insert_posts(db_session, author, ["普通", "人気"])
    db_session.execute(text("update posts set like_count = 99 where id = :id"), {"id": ids[1]})
    insert_posts(db_session, private, ["非公開の人気"])
    popular = (await client.get("/posts/popular", headers=viewer.headers)).json()
    # 開発用 DB にほかの投稿が残っていてもよいように、このテストで作った人の投稿だけを見る
    mine = [p["content"] for p in popular if p["author"]["id"] in (str(author.id), str(private.id))]
    assert mine == ["人気", "普通"]

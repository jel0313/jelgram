"""負荷テスト(ST。14-8)。ローカル環境だけで実行する(クラウドの無料枠を使わない)。

準備:
    supabase start / docker compose up -d redis
    uv run python -m scripts.seed --users 50 --posts 20   … seed_000〜seed_049 ができる
    uv run uvicorn app.main:app --port 8000 --workers 2

実行(画面 http://localhost:8089 で人数を指定):
    uv run locust -f tests/load/locustfile.py --host http://localhost:8000

画面なしで 60 秒・50 人:
    uv run locust -f tests/load/locustfile.py --host http://localhost:8000 \
        --headless -u 50 -r 10 -t 60s --csv /tmp/jelgram-load

AI チャットは Gemini の無料枠を消費するので、負荷テストには入れない。
"""

import random
import uuid

import httpx2
from locust import HttpUser, between, task

AUTH_URL = "http://127.0.0.1:54321/auth/v1"
PUBLISHABLE_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"  # ローカル専用の公開キー


class SnsUser(HttpUser):
    wait_time = between(1, 3)  # 実際の利用者のように、操作の間に 1〜3 秒あける

    def on_start(self) -> None:
        """シードのユーザーで、ローカルの Supabase Auth にログインしてトークンを得る。"""
        email = f"seed_{random.randint(0, 49):03d}@example.com"
        response = httpx2.post(
            f"{AUTH_URL}/token?grant_type=password",
            headers={"apikey": PUBLISHABLE_KEY},
            json={"email": email, "password": "password-123"},
        )
        response.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"

    @task(10)
    def timeline(self) -> None:
        self.client.get("/api/v1/posts?limit=20", name="/posts")

    @task(5)
    def feed(self) -> None:
        response = self.client.get("/api/v1/feed?limit=20", name="/feed")
        cursor = response.json().get("next_cursor") if response.ok else None
        if cursor:
            self.client.get(f"/api/v1/feed?limit=20&cursor={cursor}", name="/feed?cursor")

    @task(3)
    def profile(self) -> None:
        username = f"seed_{random.randint(0, 49):03d}"
        self.client.get(f"/api/v1/users/{username}", name="/users/{username}")
        self.client.get(f"/api/v1/users/{username}/posts", name="/users/{username}/posts")

    @task(2)
    def search(self) -> None:
        self.client.get("/api/v1/posts/search?q=ラーメン", name="/posts/search")

    @task(2)
    def like(self) -> None:
        response = self.client.get("/api/v1/posts?limit=5", name="/posts")
        if response.ok and response.json()["items"]:
            post_id = random.choice(response.json()["items"])["id"]
            self.client.post(f"/api/v1/posts/{post_id}/like", name="/posts/{id}/like")

    @task(1)
    def create_post(self) -> None:
        self.client.post(
            "/api/v1/posts",
            json={"content": "負荷テスト #load"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
            name="/posts [POST]",
        )

"""開発用のシードデータを入れる(21-4)。

    uv run python -m scripts.seed --users 20 --posts 10

- ローカル以外の DB には入れない(本番の DB を汚さないための安全装置)
- 同じコマンドを何度実行しても、ユーザーが重複しない(seed_ で始まるユーザーを作り直す)
- 作ったユーザーは、ローカルの Supabase Auth のパスワード「password-123」でログインできる
"""

import argparse
import random
import sys
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_engine

SAMPLE_TEXTS = [
    "今日のランチ #カレー",
    "朝の散歩 #朝活",
    "新しいカメラ買った #写真",
    "ラーメン食べたい #ラーメン",
    "週末は山登り #登山",
    "コード書いてる #FastAPI",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--posts", type=int, default=5, help="1人あたりの投稿数")
    args = parser.parse_args()

    settings = get_settings()
    host = urlparse(settings.database_url.get_secret_value()).hostname
    if settings.is_production or host not in ("127.0.0.1", "localhost", "host.docker.internal"):
        sys.exit(f"ローカルの DB 以外には入れません(接続先:{host})")

    random.seed(42)  # 毎回同じデータになるように
    with Session(get_engine()) as session:
        session.execute(text("delete from auth.users where email like 'seed\\_%@example.com'"))
        user_ids = []
        for i in range(args.users):
            user_id = session.execute(
                text("""
                    insert into auth.users (
                        id, instance_id, aud, role, email, encrypted_password,
                        email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                        created_at, updated_at,
                        confirmation_token, recovery_token, email_change, email_change_token_new
                    )
                    values (
                        gen_random_uuid(), '00000000-0000-0000-0000-000000000000',
                        'authenticated', 'authenticated', :email,
                        extensions.crypt('password-123', extensions.gen_salt('bf')),
                        now(), '{"provider": "email", "providers": ["email"]}',
                        jsonb_build_object('full_name', cast(:name as text)), now(), now(),
                        -- Supabase Auth は NULL だとログインで失敗するので空文字にする
                        '', '', '', ''
                    )
                    returning id
                """),
                {"email": f"seed_{i:03d}@example.com", "name": f"シード{i:03d}"},
            ).scalar_one()
            # メールとパスワードでログインするには、identities にも行が必要
            session.execute(
                text("""
                    insert into auth.identities
                        (id, user_id, identity_data, provider, provider_id, created_at, updated_at)
                    values (gen_random_uuid(), :id,
                            jsonb_build_object(
                                'sub', cast(:id as text), 'email', cast(:email as text)
                            ),
                            'email', cast(:id as text), now(), now())
                """),
                {"id": user_id, "email": f"seed_{i:03d}@example.com"},
            )
            session.execute(
                text("update profiles set username = :u, is_private = :p where id = :id"),
                {"u": f"seed_{i:03d}", "p": i % 7 == 0, "id": user_id},
            )
            user_ids.append(user_id)

        for user_id in user_ids:
            for _ in range(args.posts):
                session.execute(
                    text("""
                        insert into posts (user_id, content, created_at)
                        values (:u, :c, now() - make_interval(mins => :m))
                    """),
                    {
                        "u": user_id,
                        "c": random.choice(SAMPLE_TEXTS),
                        "m": random.randint(0, 60 * 24 * 7),
                    },
                )
            for other in random.sample(user_ids, k=min(5, len(user_ids))):
                if other != user_id:
                    session.execute(
                        text(
                            "insert into follows (follower_id, followee_id) values (:a, :b) "
                            "on conflict do nothing"
                        ),
                        {"a": user_id, "b": other},
                    )
        session.commit()
    print(f"ユーザー {args.users} 人・投稿 {args.users * args.posts} 件を入れました")


if __name__ == "__main__":
    main()

"""Outbox パターン(20-4)。

「DB を更新して、プッシュ通知も送る」をそのまま書くと、次のどちらかが起きうる。
- DB は確定したのに、送信の前にプロセスが落ちて通知が届かない
- 通知は送ったのに、DB がロールバックされて存在しないデータの通知になる

そこで、送信そのものではなく「送るべきこと」を同じトランザクションで outbox_events に書く。
ワーカー(worker/tasks.py の relay_outbox)が後から取り出して実行し、
成功したら processed_at を入れる。

    service ── insert 本体 ──┐
            └─ insert outbox ┴─ commit(両方そろって確定)
    worker  ── select ... for update skip locked → 実行 → processed_at
"""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# イベントの種類
NOTIFICATION_CREATED = "notification.created"  # payload: {"notification_id": int}
MEDIA_DELETE = "media.delete"  # payload: {"paths": [str, ...]}
USER_PURGE = "user.purge"  # payload: {"user_id": str}
MEDIA_PROCESS = "media.process"  # payload: {"media_id": str}
POST_MODERATE = "post.moderate"  # payload: {"post_id": int}


def enqueue(session: Session, event_type: str, payload: dict[str, Any]) -> None:
    """イベントを追加する(commit は呼び出し元)。"""
    session.execute(
        text("insert into outbox_events (event_type, payload) values (:t, cast(:p as jsonb))"),
        {"t": event_type, "p": json.dumps(payload, default=str)},
    )

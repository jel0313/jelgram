"""Webhook の受信(11-6)。外部のモデレーションサービスが「この投稿は不適切」と知らせてくる想定。

JWT ではなく、共有鍵の HMAC 署名で「本当にそのサービスから来たか」を確かめる。

    送信側:signature = HMAC-SHA256(共有鍵, "<タイムスタンプ>.<本文>")
            ヘッダー X-Webhook-Timestamp・X-Webhook-Signature に入れて送る
    受信側:① 同じ計算をして一致するか(改ざん・なりすまし対策)
            ② タイムスタンプが5分以内か(盗んだリクエストの再送対策)
            ③ event_id が初めてか(同じイベントの重複受信対策。送信側は失敗すると再送してくる)
"""

import hashlib
import hmac
import json
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text

from app.admin import service as admin_service
from app.core.config import SettingsDep
from app.core.db import DbSessionDep
from app.core.exceptions import BadRequestError, ServiceUnavailableError, UnauthorizedError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

TOLERANCE_SECONDS = 300


class ModerationEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    type: Literal["post.flagged"]
    post_id: int
    reason: str = Field(max_length=500)


class WebhookAck(BaseModel):
    status: Literal["processed", "duplicate"]


def verify_signature(secret: str, timestamp: str, body: bytes, signature: str, now: float) -> None:
    if not timestamp.isdigit() or abs(now - int(timestamp)) > TOLERANCE_SECONDS:
        raise UnauthorizedError("タイムスタンプが古いか不正です")
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    # == で比べると、一致するまでの時間の差から署名を推測される。必ず compare_digest を使う
    if not hmac.compare_digest(expected, signature):
        raise UnauthorizedError("署名が一致しません")


async def raw_body(request: Request) -> bytes:
    """受け取ったままの本文。署名はこのバイト列で計算するので、JSON として読み直す前に取る。"""
    return await request.body()


@router.post("/moderation", response_model=WebhookAck)
def receive_moderation(
    body: Annotated[bytes, Depends(raw_body)],
    session: DbSessionDep,
    settings: SettingsDep,
    x_webhook_timestamp: Annotated[str, Header()],
    x_webhook_signature: Annotated[str, Header()],
) -> WebhookAck:
    """モデレーションの結果を受け取る。"""
    if settings.webhook_secret is None:
        raise ServiceUnavailableError("Webhook は設定されていません")
    verify_signature(
        settings.webhook_secret.get_secret_value(),
        x_webhook_timestamp,
        body,
        x_webhook_signature,
        time.time(),
    )
    try:
        event = ModerationEvent.model_validate_json(body)
    except ValidationError as e:
        raise BadRequestError("本文の形式が正しくありません") from e

    inserted = session.execute(
        text("""
            insert into webhook_events (provider, event_id, payload)
            values ('moderation', :id, cast(:payload as jsonb))
            on conflict do nothing returning event_id
        """),
        {"id": event.event_id, "payload": json.dumps(json.loads(body))},
    ).one_or_none()
    if inserted is None:
        return WebhookAck(status="duplicate")  # 2回目以降は何もしないで 200 を返す(再送を止める)
    admin_service.hide_post_automatically(session, event.post_id, "webhook", event.reason)
    session.commit()
    return WebhookAck(status="processed")

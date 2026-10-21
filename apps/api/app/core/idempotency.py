"""冪等性キー(10-4)。投稿ボタンの二度押し・通信の再送で、同じ投稿が2つできないようにする。

クライアントは操作ごとに一意なキー(UUID など)を `Idempotency-Key` ヘッダーで送る。

    1回目:キーを登録 → 処理 → 結果も保存 → commit(全部同じトランザクション)
    2回目:キーが登録済み → 処理せず、保存した結果をそのまま返す
    同時に来た:主キーの重複で2回目の insert が待たされ、1回目の commit 後に「登録済み」になる
    同じキーで中身が違う:クライアントの誤りなので 422
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError


class IdempotencyKeyReusedError(AppError):
    status_code = 422
    code = "idempotency_key_reused"
    message = "同じ Idempotency-Key が、別の内容のリクエストに使われています"


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: Any


def request_hash(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def begin(session: Session, user_id: UUID, key: str, hash_: str) -> StoredResponse | None:
    """キーを登録する。登録済みなら、保存してある結果を返す。"""
    inserted = session.execute(
        text("""
            insert into idempotency_keys (user_id, key, request_hash)
            values (:user_id, :key, :hash)
            on conflict (user_id, key) do nothing
            returning key
        """),
        {"user_id": user_id, "key": key, "hash": hash_},
    ).one_or_none()
    if inserted is not None:
        return None  # 1回目

    row = (
        session.execute(
            text("""
                select request_hash, response_status, response_body from idempotency_keys
                where user_id = :user_id and key = :key
            """),
            {"user_id": user_id, "key": key},
        )
        .mappings()
        .one()
    )
    if row["request_hash"] != hash_:
        raise IdempotencyKeyReusedError
    if row["response_status"] is None:
        raise ConflictError("同じリクエストを処理中です")
    return StoredResponse(status_code=row["response_status"], body=row["response_body"])


def save(session: Session, user_id: UUID, key: str, status_code: int, body: Any) -> None:
    """処理の結果を保存する(commit は呼び出し元。本体の処理と一緒に確定させる)。"""
    session.execute(
        text("""
            update idempotency_keys
            set response_status = :status, response_body = cast(:body as jsonb)
            where user_id = :user_id and key = :key
        """),
        {
            "user_id": user_id,
            "key": key,
            "status": status_code,
            "body": json.dumps(body, default=str, ensure_ascii=False),
        },
    )

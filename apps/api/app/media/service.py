"""画像の業務ロジック(9章)。

アップロードは2通りある。
    A. API 経由(9-1):ブラウザ → API(検証)→ ストレージ
    B. 直接(9-7)  :ブラウザ → API(署名付き URL の発行)→ ブラウザがストレージへ PUT
                     → API の complete(ストレージから読んで検証)
どちらも、検証に通った画像だけを media に登録し、加工(EXIF 削除・サムネイル)はワーカーに任せる。
"""

import logging
import uuid
from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import outbox
from app.media import repository
from app.media.constants import ALLOWED_TYPES, MAX_IMAGE_BYTES
from app.media.exceptions import ImageTooLargeError, MediaNotFoundError
from app.media.schemas import (
    MediaOut,
    MediaResponse,
    MediaUrlResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.media.storage import StorageClient, StorageError
from app.media.validation import validate_image

logger = logging.getLogger(__name__)


def new_storage_path(owner_id: UUID, extension: str) -> str:
    """保存名は UUID にする(9-4)。

    クライアントのファイル名(../../etc/passwd・同名の上書き・個人名入り)を一切使わない。
    """
    return f"{owner_id}/{uuid.uuid4().hex}.{extension}"


def upload_media(
    session: Session,
    storage: StorageClient,
    *,
    owner_id: UUID,
    data: bytes,
    filename: str | None,
    content_type: str | None,
    expires_in: int,
) -> MediaResponse:
    """A. API 経由のアップロード。"""
    image = validate_image(data, filename=filename, declared_type=content_type)
    path = new_storage_path(owner_id, image.extension)
    storage.upload(path, data, image.content_type)
    try:
        row = repository.insert_media(
            session,
            owner_id=owner_id,
            path=path,
            content_type=image.content_type,
            size_bytes=len(data),
            width=image.width,
            height=image.height,
        )
        outbox.enqueue(session, outbox.MEDIA_PROCESS, {"media_id": str(row["id"])})
        session.commit()
    except Exception:
        # DB に登録できなかったら、置いたファイルを消して元に戻す(ストレージはロールバックできない)
        session.rollback()
        _delete_quietly(storage, [path])
        raise
    return to_media_response(row, storage, expires_in)


def create_upload_url(
    session: Session, storage: StorageClient, *, owner_id: UUID, body: UploadUrlRequest
) -> UploadUrlResponse:
    """B. 直接アップロード用の URL を発行する。サイズ・形式は complete で改めて確かめる。"""
    extension = ALLOWED_TYPES[body.content_type][0]
    path = new_storage_path(owner_id, extension)
    upload_url = storage.signed_upload_url(path)
    row = repository.insert_media(
        session,
        owner_id=owner_id,
        path=path,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        width=None,
        height=None,
    )
    session.commit()
    return UploadUrlResponse(media_id=row["id"], upload_url=upload_url)


def complete_upload(
    session: Session, storage: StorageClient, *, owner_id: UUID, media_id: UUID, expires_in: int
) -> MediaResponse:
    """B. 直接アップロードの完了。実物をストレージから読んで、A と同じ検証をする。"""
    row = repository.get_media(session, media_id)
    if row is None or row["owner_id"] != owner_id:
        raise MediaNotFoundError
    if row["status"] != "pending" or row["width"] is not None:
        return to_media_response(row, storage, expires_in)  # 2回目以降は何もしない(冪等)

    try:
        data = storage.download(row["path"])
    except StorageError as e:
        raise MediaNotFoundError("アップロードされた画像が見つかりません") from e
    try:
        if len(data) > MAX_IMAGE_BYTES:
            raise ImageTooLargeError
        image = validate_image(data, filename=None, declared_type=row["content_type"])
    except Exception:
        # 検証に通らなかったファイルは残さない
        _delete_quietly(storage, [row["path"]])
        repository.update_processed(session, media_id, status="failed")
        session.commit()
        raise

    repository.update_processed(
        session,
        media_id,
        status="pending",
        width=image.width,
        height=image.height,
        size_bytes=len(data),
    )
    outbox.enqueue(session, outbox.MEDIA_PROCESS, {"media_id": str(media_id)})
    session.commit()
    updated = repository.get_media(session, media_id)
    if updated is None:
        raise MediaNotFoundError
    return to_media_response(updated, storage, expires_in)


def get_media_url(
    session: Session, storage: StorageClient, *, viewer_id: UUID, media_id: UUID, expires_in: int
) -> MediaUrlResponse:
    """画像取得 API(9-6)。見てよい画像なら、期限付きの URL を返す。

    見てはいけない画像も「ない」と同じ 404 にする(存在するかどうかを推測させない)。
    """
    row = repository.get_visible_media(session, media_id, viewer_id)
    if row is None or row["status"] == "failed":
        raise MediaNotFoundError
    paths = [p for p in (row["path"], row["thumbnail_path"]) if p]
    urls = storage.signed_urls(paths, expires_in)
    if row["path"] not in urls:
        raise MediaNotFoundError
    return MediaUrlResponse(
        url=urls[row["path"]],
        thumbnail_url=urls.get(row["thumbnail_path"] or ""),
        expires_in=expires_in,
    )


def sign_media(
    storage: StorageClient, rows: Iterable[Mapping[Any, Any]], expires_in: int
) -> dict[UUID, MediaOut]:
    """画像の行から、署名付き URL 付きの MediaOut を作る。何枚あっても通信は1回。

    ストレージが落ちていても投稿の一覧は返したいので、その場合は URL を null にする。
    """
    rows = list(rows)
    paths = [p for row in rows for p in (row["path"], row.get("thumbnail_path")) if p]
    try:
        urls = storage.signed_urls(paths, expires_in)
    except StorageError:
        urls = {}
    return {
        row["id"]: MediaOut(
            id=row["id"],
            url=urls.get(row["path"]),
            thumbnail_url=urls.get(row.get("thumbnail_path") or ""),
            width=row.get("width"),
            height=row.get("height"),
        )
        for row in rows
    }


def to_media_response(
    row: Mapping[Any, Any], storage: StorageClient, expires_in: int
) -> MediaResponse:
    signed = sign_media(storage, [row], expires_in)[row["id"]]
    return MediaResponse(
        **signed.model_dump(),
        status=row["status"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        created_at=row["created_at"],
    )


def _delete_quietly(storage: StorageClient, paths: list[str]) -> None:
    try:
        storage.delete(paths)
    except StorageError:
        logger.warning("ストレージのファイルを消せませんでした", extra={"paths": paths})

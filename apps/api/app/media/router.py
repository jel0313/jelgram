"""画像の API(9章)。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.auth.dependencies import CurrentUserDep, rate_limit
from app.core.config import SettingsDep
from app.core.db import DbSessionDep
from app.core.schemas import COMMON_ERROR_RESPONSES, ErrorResponse
from app.media import service
from app.media.constants import MAX_IMAGE_BYTES
from app.media.schemas import MediaResponse, MediaUrlResponse, UploadUrlRequest, UploadUrlResponse
from app.media.storage import StorageDep

router = APIRouter(prefix="/media", tags=["media"], responses=COMMON_ERROR_RESPONSES)

_upload_limit = Depends(rate_limit("uploads", "rate_limit_uploads_per_minute"))


@router.post(
    "",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_upload_limit],
    responses={
        413: {"model": ErrorResponse, "description": "5MB を超える"},
        415: {"model": ErrorResponse, "description": "許可されていない形式・中身と拡張子の不一致"},
    },
)
def upload_media(
    file: Annotated[UploadFile, File(description="画像(JPEG・PNG・WebP・GIF、5MB まで)")],
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> MediaResponse:
    """画像をアップロードする(9-1)。返ってきた id を投稿の media_ids に入れる。"""
    # 上限 + 1 バイトまでだけ読む。大きいファイルを全部メモリに載せない
    data = file.file.read(MAX_IMAGE_BYTES + 1)
    return service.upload_media(
        session,
        storage,
        owner_id=user.id,
        data=data,
        filename=file.filename,
        content_type=file.content_type,
        expires_in=settings.media_signed_url_expires_seconds,
    )


@router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_upload_limit],
)
def create_upload_url(
    body: UploadUrlRequest, user: CurrentUserDep, session: DbSessionDep, storage: StorageDep
) -> UploadUrlResponse:
    """ブラウザからストレージへ直接アップロードするための、署名付き URL を発行する(9-7)。"""
    return service.create_upload_url(session, storage, owner_id=user.id, body=body)


@router.post("/{media_id}/complete", response_model=MediaResponse)
def complete_upload(
    media_id: UUID,
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> MediaResponse:
    """直接アップロードが終わったことを知らせる。中身を検証して、だめなら消す。"""
    return service.complete_upload(
        session,
        storage,
        owner_id=user.id,
        media_id=media_id,
        expires_in=settings.media_signed_url_expires_seconds,
    )


@router.get(
    "/{media_id}",
    response_model=MediaUrlResponse,
    responses={404: {"model": ErrorResponse, "description": "ない・見る権限がない"}},
)
def get_media_url(
    media_id: UUID,
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> MediaUrlResponse:
    """画像の URL を取得する(9-6)。非公開アカウントの画像は、承認済みフォロワーだけが取れる。"""
    return service.get_media_url(
        session,
        storage,
        viewer_id=user.id,
        media_id=media_id,
        expires_in=settings.media_signed_url_expires_seconds,
    )

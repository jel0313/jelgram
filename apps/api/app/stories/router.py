"""ストーリーの API(24時間で消える投稿。11-5)。

小さな機能なので、service・repository の中身もこのフォルダの service.py にまとめている。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.auth.dependencies import CurrentUserDep, rate_limit
from app.core.config import SettingsDep
from app.core.db import DbSessionDep
from app.core.schemas import COMMON_ERROR_RESPONSES
from app.media.storage import StorageDep
from app.stories import service
from app.stories.service import StoryResponse

router = APIRouter(prefix="/stories", tags=["stories"], responses=COMMON_ERROR_RESPONSES)


class StoryCreate(BaseModel):
    media_id: UUID


@router.post(
    "",
    response_model=StoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("stories", "rate_limit_stories_per_minute"))],
)
def create_story(
    body: StoryCreate,
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> StoryResponse:
    """ストーリーを投稿する。24時間後に見えなくなり、定期ジョブで削除される。"""
    return service.create_story(
        session, storage, user.id, body.media_id, settings.media_signed_url_expires_seconds
    )


@router.get("", response_model=list[StoryResponse])
def list_stories(
    user: CurrentUserDep, session: DbSessionDep, storage: StorageDep, settings: SettingsDep
) -> list[StoryResponse]:
    """フォロー中の人と自分の、期限内のストーリー。"""
    return service.list_stories(
        session, storage, user.id, settings.media_signed_url_expires_seconds
    )


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(story_id: int, user: CurrentUserDep, session: DbSessionDep) -> None:
    service.delete_story(session, user.id, story_id)

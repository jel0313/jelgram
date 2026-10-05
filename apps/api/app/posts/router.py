from fastapi import APIRouter

from app.auth.dependencies import CurrentUserDep
from app.core.db import DbSessionDep
from app.posts import service
from app.posts.schemas import PostResponse

router = APIRouter(
    prefix="/posts",
    tags=["posts"],
)


@router.get("", response_model=list[PostResponse])
def get_posts(user: CurrentUserDep, session: DbSessionDep) -> list[PostResponse]:
    """タイムラインの投稿を新しい順に返す。"""
    return service.get_timeline(session, user.id)

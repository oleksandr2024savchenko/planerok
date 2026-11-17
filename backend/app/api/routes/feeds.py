from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.api.deps import SessionDep, UserIdDep
from app.models import ExternalEvent
from app.schemas import FeedCreate, FeedRead
from app.services.external_calendars import FeedError, add_feed, delete_feed, feed_host, list_feeds

router = APIRouter(prefix="/calendar/feeds", tags=["calendar-feeds"])


def _http(exc: FeedError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("", response_model=list[FeedRead])
async def get_feeds(session: SessionDep, user_id: UserIdDep) -> list[FeedRead]:
    return await list_feeds(session, user_id)


@router.post("", response_model=FeedRead, status_code=status.HTTP_201_CREATED)
async def create_feed(payload: FeedCreate, session: SessionDep, user_id: UserIdDep) -> FeedRead:
    try:
        feed = await add_feed(session, user_id, payload.url, payload.name)
    except FeedError as exc:
        raise _http(exc) from exc
    count = await session.scalar(
        select(func.count()).select_from(ExternalEvent).where(ExternalEvent.calendar_id == feed.id)
    )
    return FeedRead(
        id=feed.id,
        name=feed.name,
        host=feed_host(feed.url),
        last_sync_at=feed.last_sync_at,
        last_error=feed.last_error,
        event_count=int(count or 0),
    )


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_feed(feed_id: int, session: SessionDep, user_id: UserIdDep) -> Response:
    removed = await delete_feed(session, user_id, feed_id)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Календар не знайдено")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

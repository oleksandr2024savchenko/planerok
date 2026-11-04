import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, status

from app.api.deps import SessionDep, UserIdDep
from app.config import get_settings
from app.schemas import CalendarStatusRead
from app.services import google_calendar

logger = logging.getLogger(__name__)

router = APIRouter(tags=["google-calendar"])


async def _sync_safely() -> None:
    try:
        await google_calendar.sync_from_google(None)
    except google_calendar.GoogleCalendarError:
        logger.warning("Google push sync failed", exc_info=True)


@router.get("/calendar/status", response_model=CalendarStatusRead)
async def calendar_status(session: SessionDep, user_id: UserIdDep) -> CalendarStatusRead:
    del user_id
    connected, live, last_sync = await google_calendar.calendar_status(session)
    return CalendarStatusRead(connected=connected, live=live, last_sync_at=last_sync)


@router.post("/webhooks/google-calendar", status_code=status.HTTP_200_OK)
async def google_calendar_webhook(
    background: BackgroundTasks,
    x_goog_channel_token: str | None = Header(default=None),
    x_goog_resource_state: str | None = Header(default=None),
) -> dict[str, bool]:
    """Google push notification. The body is empty; headers carry the channel state."""
    should_sync = await google_calendar.accept_push(x_goog_channel_token, x_goog_resource_state)
    if should_sync:
        background.add_task(_sync_safely)
    return {"ok": True}


@router.get("/calendar/oauth/start")
async def oauth_start(setup_token: str = Query()) -> dict[str, str]:
    expected = get_settings().google_channel_token
    if not expected or setup_token != expected:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    try:
        url = await asyncio.to_thread(google_calendar.authorization_url, setup_token)
    except google_calendar.GoogleCalendarError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return {"url": url}


@router.get("/calendar/oauth/callback")
async def oauth_callback(
    session: SessionDep,
    code: str = Query(),
    state: str = Query(default=""),
) -> dict[str, str]:
    expected = get_settings().google_channel_token
    if not expected or state != expected:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    try:
        refresh = await asyncio.to_thread(google_calendar.exchange_code, code)
    except google_calendar.GoogleCalendarError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    await google_calendar.store_refresh_token(session, refresh)
    return {"status": "connected"}

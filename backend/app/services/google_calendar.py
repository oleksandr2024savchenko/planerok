"""Two-way Google Calendar sync. All instants are Europe/Vienna."""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TIMEZONE, get_settings
from app.db import session_factory
from app.models import GoogleCalendarState, Task
from app.schemas import _to_vienna

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_TZ = "Europe/Vienna"
_FULL_SYNC_PAST = timedelta(days=1)
_FULL_SYNC_FUTURE = timedelta(days=90)
_WATCH_TTL = timedelta(days=6)


class GoogleCalendarError(RuntimeError):
    pass


@dataclass(slots=True)
class GoogleEventChange:
    event_id: str
    cancelled: bool
    title: str
    description: str | None
    start: datetime | None
    end: datetime | None
    planer_task_id: int | None


def google_enabled() -> bool:
    settings = get_settings()
    if settings.google_service_account_file:
        return True
    return bool(settings.google_client_id and settings.google_client_secret)


def _service_account_path() -> Path | None:
    raw = get_settings().google_service_account_file
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def is_configured() -> bool:
    settings = get_settings()
    if _service_account_path() is not None:
        return True
    return bool(settings.google_client_id and settings.google_client_secret and settings.google_refresh_token)


def owner_user_id() -> int | None:
    settings = get_settings()
    return settings.google_owner_user_id or settings.dev_user_id


def _rfc3339(value: datetime) -> str:
    return value.astimezone(TIMEZONE).isoformat(timespec="seconds")


def _same_minute(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is right
    a = left.astimezone(TIMEZONE).replace(second=0, microsecond=0)
    b = right.astimezone(TIMEZONE).replace(second=0, microsecond=0)
    return a == b


def default_reminder(start: datetime, *, now: datetime | None = None) -> datetime | None:
    """Nag shortly before the event, or at the start if that window has passed."""
    current = now or datetime.now(TIMEZONE)
    early = start - timedelta(minutes=15)
    if early > current:
        return early
    if start > current:
        return start
    return None


def parse_google_event(item: dict) -> GoogleEventChange | None:
    event_id = item.get("id")
    if not event_id:
        return None
    private = (item.get("extendedProperties") or {}).get("private") or {}
    raw_task_id = private.get("planerTaskId")
    try:
        task_id = int(raw_task_id) if raw_task_id is not None else None
    except (TypeError, ValueError):
        task_id = None
    cancelled = item.get("status") == "cancelled"
    start, end = (None, None) if cancelled else _google_range(item.get("start") or {}, item.get("end") or {})
    if not cancelled and start is None:
        return None
    title = (item.get("summary") or "Подія").strip()[:255] or "Подія"
    description = (item.get("description") or "").strip() or None
    return GoogleEventChange(
        event_id=event_id,
        cancelled=cancelled,
        title=title,
        description=description,
        start=start,
        end=end,
        planer_task_id=task_id,
    )


def _google_range(start: dict, end: dict) -> tuple[datetime | None, datetime | None]:
    if start.get("date"):
        # Google's all-day `end.date` is exclusive. Show a one-hour morning block.
        day = datetime.fromisoformat(start["date"])
        start_at = datetime(day.year, day.month, day.day, 7, 0, tzinfo=TIMEZONE)
        return start_at, start_at + timedelta(hours=1)
    if raw := start.get("dateTime"):
        start_at = _to_vienna(datetime.fromisoformat(raw))
        end_at = _to_vienna(datetime.fromisoformat(end["dateTime"])) if end.get("dateTime") else None
        return start_at, end_at
    return None, None


def build_event_body(task: Task) -> dict | None:
    start = _to_vienna(task.start_time) or _timed_deadline(task)
    if start is None:
        return None
    end = _to_vienna(task.end_time) or start + timedelta(hours=1)
    if end <= start:
        end = start + timedelta(hours=1)
    body: dict = {
        "summary": task.title,
        "start": {"dateTime": _rfc3339(start), "timeZone": CALENDAR_TZ},
        "end": {"dateTime": _rfc3339(end), "timeZone": CALENDAR_TZ},
        "extendedProperties": {"private": {"planerTaskId": str(task.id), "source": "planer"}},
    }
    if task.description:
        body["description"] = task.description
    return body


def _timed_deadline(task: Task) -> datetime | None:
    deadline = _to_vienna(task.deadline)
    if deadline is None:
        return None
    local = deadline.astimezone(TIMEZONE)
    if local.hour == 23 and local.minute == 59:
        return None
    return deadline


def _client_config() -> dict:
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def build_oauth_flow() -> Flow:
    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret and settings.google_oauth_redirect_uri):
        raise GoogleCalendarError("OAuth client is not configured")
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,
    )


def authorization_url(state: str) -> str:
    flow = build_oauth_flow()
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return url


def exchange_code(code: str) -> str:
    flow = build_oauth_flow()
    flow.fetch_token(code=code)
    refresh = flow.credentials.refresh_token
    if not refresh:
        raise GoogleCalendarError("Google did not return a refresh token")
    return refresh


def _credentials(refresh_token: str | None) -> Credentials | ServiceAccountCredentials:
    path = _service_account_path()
    if path is not None:
        creds = ServiceAccountCredentials.from_service_account_file(path, scopes=SCOPES)
        email = get_settings().google_impersonate_email
        return creds.with_subject(email) if email else creds
    settings = get_settings()
    token = refresh_token or settings.google_refresh_token
    if not (settings.google_client_id and settings.google_client_secret and token):
        raise GoogleCalendarError("Google Calendar is not configured")
    return Credentials(
        token=None,
        refresh_token=token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )


def _service(creds: Credentials | ServiceAccountCredentials):
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


async def _state(session: AsyncSession) -> GoogleCalendarState:
    state = await session.scalar(select(GoogleCalendarState).limit(1))
    if state is None:
        state = GoogleCalendarState(calendar_id=get_settings().google_calendar_id)
        session.add(state)
        await session.flush()
    return state


def _fetch_changes(creds: Credentials | ServiceAccountCredentials, calendar_id: str, sync_token: str | None):
    service = _service(creds)
    kwargs: dict = {
        "calendarId": calendar_id,
        "singleEvents": True,
        "showDeleted": True,
        "maxResults": 250,
    }
    if sync_token:
        kwargs["syncToken"] = sync_token
    else:
        now = datetime.now(TIMEZONE)
        kwargs["timeMin"] = _rfc3339(now - _FULL_SYNC_PAST)
        kwargs["timeMax"] = _rfc3339(now + _FULL_SYNC_FUTURE)
    items: list[dict] = []
    while True:
        page = service.events().list(**kwargs).execute()
        items.extend(page.get("items", []))
        token = page.get("nextPageToken")
        if not token:
            return items, page.get("nextSyncToken")
        kwargs["pageToken"] = token


def _insert_event(creds, calendar_id: str, body: dict) -> str:
    created = _service(creds).events().insert(calendarId=calendar_id, body=body).execute()
    return created["id"]


def _patch_event(creds, calendar_id: str, event_id: str, body: dict) -> None:
    _service(creds).events().patch(calendarId=calendar_id, eventId=event_id, body=body).execute()


def _remove_event(creds, calendar_id: str, event_id: str) -> None:
    try:
        _service(creds).events().delete(calendarId=calendar_id, eventId=event_id).execute()
    except HttpError as exc:
        if getattr(exc.resp, "status", None) in (404, 410):
            return
        raise


def _stop_channel(creds, channel_id: str, resource_id: str) -> None:
    try:
        _service(creds).channels().stop(body={"id": channel_id, "resourceId": resource_id}).execute()
    except HttpError as exc:
        if getattr(exc.resp, "status", None) in (404, 410):
            return
        logger.warning("Failed to stop Google channel %s: %s", channel_id, exc)


def _start_watch(creds, calendar_id: str, channel_id: str, address: str, token: str) -> dict:
    return (
        _service(creds)
        .events()
        .watch(
            calendarId=calendar_id,
            body={"id": channel_id, "type": "web_hook", "address": address, "token": token},
        )
        .execute()
    )


async def _connection() -> tuple[str | None, str]:
    settings = get_settings()
    async with session_factory() as session:
        state = await session.scalar(select(GoogleCalendarState).limit(1))
        if state is None:
            state = GoogleCalendarState(calendar_id=settings.google_calendar_id)
            session.add(state)
            await session.commit()
            await session.refresh(state)
        return state.refresh_token, state.calendar_id or settings.google_calendar_id


async def create_google_event(task: Task) -> str | None:
    body = build_event_body(task)
    if body is None:
        return None
    refresh_token, calendar_id = await _connection()
    creds = _credentials(refresh_token)
    try:
        return await asyncio.to_thread(_insert_event, creds, calendar_id, body)
    except (HttpError, GoogleAuthError) as exc:
        logger.exception("Failed to create Google event for task %s", task.id)
        raise GoogleCalendarError("Не вдалося створити подію в Google Calendar") from exc


async def update_google_event(task: Task) -> None:
    if not task.google_event_id:
        return
    body = build_event_body(task)
    if body is None:
        await delete_google_event(task.google_event_id)
        return
    refresh_token, calendar_id = await _connection()
    creds = _credentials(refresh_token)
    try:
        await asyncio.to_thread(_patch_event, creds, calendar_id, task.google_event_id, body)
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 404:
            new_id = await create_google_event(task)
            task.google_event_id = new_id
            return
        logger.exception("Failed to update Google event %s", task.google_event_id)
        raise GoogleCalendarError("Не вдалося оновити подію в Google Calendar") from exc


async def delete_google_event(google_event_id: str) -> None:
    try:
        refresh_token, calendar_id = await _connection()
        creds = _credentials(refresh_token)
    except GoogleCalendarError:
        return
    try:
        await asyncio.to_thread(_remove_event, creds, calendar_id, google_event_id)
    except (HttpError, GoogleAuthError):
        logger.exception("Failed to delete Google event %s", google_event_id)


async def sync_from_google(sync_token: str | None = None) -> str | None:
    """Pull new and changed events. Returns the next sync token."""
    owner = owner_user_id()
    async with session_factory() as session:
        state = await _state(session)
        token = sync_token if sync_token is not None else state.sync_token
        calendar_id = get_settings().google_calendar_id or state.calendar_id
        try:
            creds = _credentials(state.refresh_token)
            try:
                items, next_token = await asyncio.to_thread(_fetch_changes, creds, calendar_id, token)
            except HttpError as exc:
                if token and getattr(exc.resp, "status", None) == 410:
                    logger.info("Google sync token expired, running a full sync")
                    items, next_token = await asyncio.to_thread(_fetch_changes, creds, calendar_id, None)
                else:
                    raise
        except (HttpError, GoogleAuthError, GoogleCalendarError) as exc:
            state.last_error = str(exc)[:500]
            await session.commit()
            logger.exception("Google Calendar sync failed")
            raise GoogleCalendarError("Не вдалося синхронізувати Google Calendar") from exc

        changed: list[Task] = []
        removed: list[int] = []
        if owner is None:
            logger.warning("GOOGLE_OWNER_USER_ID is empty; imported events will not be stored")
        else:
            for item in items:
                change = parse_google_event(item)
                if change is None:
                    continue
                task, deleted_id = await _apply_change(session, change, owner=owner, sync_token=next_token)
                if deleted_id is not None:
                    removed.append(deleted_id)
                elif task is not None:
                    changed.append(task)

        state.sync_token = next_token
        state.calendar_id = calendar_id
        state.last_sync_at = datetime.now(TIMEZONE)
        state.last_error = None
        await session.commit()

    from app.scheduler import cancel_reminder
    from app.services.tasks import sync_reminder

    for task_id in removed:
        cancel_reminder(task_id)
    for task in changed:
        sync_reminder(task)
    logger.info("Google sync applied %s changes (%s removed)", len(changed), len(removed))
    return next_token


async def _apply_change(
    session: AsyncSession,
    change: GoogleEventChange,
    *,
    owner: int,
    sync_token: str | None,
) -> tuple[Task | None, int | None]:
    task = await session.scalar(select(Task).where(Task.google_event_id == change.event_id))
    if task is None and change.planer_task_id is not None:
        candidate = await session.get(Task, change.planer_task_id)
        if candidate is not None and (candidate.google_event_id in (None, change.event_id)):
            task = candidate

    if change.cancelled:
        if task is None:
            return None, None
        task_id = task.id
        await session.delete(task)
        return None, task_id

    start = change.start
    end = change.end or (start + timedelta(hours=1) if start else None)
    if task is None:
        if start is None:
            return None, None
        task = Task(
            user_id=owner,
            title=change.title,
            description=change.description,
            category="особисте",
            deadline=end,
            start_time=start,
            end_time=end,
            remind_at=default_reminder(start),
            google_event_id=change.event_id,
            sync_token=sync_token,
        )
        session.add(task)
        await session.flush()
        return task, None

    start_changed = not _same_minute(task.start_time, start)
    task.title = change.title
    task.description = change.description
    task.start_time = start
    task.end_time = end
    task.deadline = end or task.deadline
    task.google_event_id = change.event_id
    task.sync_token = sync_token
    if start_changed and start is not None:
        task.remind_at = default_reminder(start)
    return task, None


async def ensure_watch() -> None:
    settings = get_settings()
    if not settings.google_webhook_url:
        logger.info("GOOGLE_WEBHOOK_URL is empty; push sync is off")
        return
    async with session_factory() as session:
        state = await _state(session)
        creds = _credentials(state.refresh_token)
        calendar_id = settings.google_calendar_id or state.calendar_id
        token = settings.google_channel_token or state.channel_token or secrets.token_urlsafe(24)
        expiration = state.channel_expiration
        fresh = expiration is not None and expiration > datetime.now(TIMEZONE) + timedelta(days=1)
        if state.channel_id and state.resource_id and fresh:
            return
        if state.channel_id and state.resource_id:
            await asyncio.to_thread(_stop_channel, creds, state.channel_id, state.resource_id)
        channel_id = str(uuid.uuid4())
        try:
            watched = await asyncio.to_thread(
                _start_watch, creds, calendar_id, channel_id, settings.google_webhook_url, token
            )
        except (HttpError, GoogleAuthError) as exc:
            state.last_error = str(exc)[:500]
            await session.commit()
            logger.exception("Failed to start Google Calendar watch")
            return
        expires_ms = int(watched.get("expiration") or 0)
        state.channel_id = channel_id
        state.resource_id = watched.get("resourceId")
        state.channel_token = token
        state.calendar_id = calendar_id
        state.channel_expiration = (
            datetime.fromtimestamp(expires_ms / 1000, tz=TIMEZONE) if expires_ms else datetime.now(TIMEZONE) + _WATCH_TTL
        )
        await session.commit()
        logger.info("Google Calendar watch active until %s", state.channel_expiration)


async def store_refresh_token(session: AsyncSession, refresh_token: str) -> None:
    state = await _state(session)
    state.refresh_token = refresh_token
    await session.commit()


async def calendar_status(session: AsyncSession) -> tuple[bool, bool, datetime | None]:
    state = await session.scalar(select(GoogleCalendarState).limit(1))
    connected = _service_account_path() is not None or bool(
        get_settings().google_client_id
        and get_settings().google_client_secret
        and ((state and state.refresh_token) or get_settings().google_refresh_token)
    )
    expiration = state.channel_expiration if state else None
    live = bool(state and state.resource_id and expiration and expiration > datetime.now(TIMEZONE))
    return connected, live, state.last_sync_at if state else None


async def accept_push(channel_token: str | None, resource_state: str | None) -> bool:
    """Return True when the notification should trigger a sync."""
    if resource_state == "sync":
        return False
    async with session_factory() as session:
        state = await session.scalar(select(GoogleCalendarState).limit(1))
    expected = (state.channel_token if state else None) or get_settings().google_channel_token
    if expected and channel_token != expected:
        logger.warning("Ignored Google push with an unexpected channel token")
        return False
    return True


async def bootstrap_google() -> None:
    if not google_enabled():
        return
    try:
        if is_configured() or _service_account_path() is not None:
            await ensure_watch()
            await sync_from_google(None)
    except Exception:
        logger.exception("Google Calendar bootstrap failed")


async def refresh_google_watch() -> None:
    """APScheduler safety net: renew the watch channel and pull incremental changes."""
    await bootstrap_google()

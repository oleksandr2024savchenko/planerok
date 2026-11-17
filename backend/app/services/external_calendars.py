"""Subscribe to an external calendar by its iCal link.

Events stay owned by the feed (title and time are not editable here) but can be
marked done. That flag is local and is carried across feed refreshes.
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import logging
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import recurring_ical_events
from icalendar import Calendar
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TIMEZONE
from app.db import session_factory
from app.models import ExternalCalendar, ExternalEvent
from app.models import Priority
from app.schemas import FeedRead, TaskRead, TaskScope

logger = logging.getLogger(__name__)

MAX_FEEDS = 8
MAX_BYTES = 2_000_000
MAX_EVENTS = 400
MAX_ALL_DAY_SPAN = 14
PAST = timedelta(days=1)
FUTURE = timedelta(days=120)
_PUBLIC_PORTS = {None, 80, 443}


class FeedError(ValueError):
    pass


class _Redirect(Exception):
    def __init__(self, url: str) -> None:
        self.url = url


class _StopRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise _Redirect(urllib.parse.urljoin(req.full_url, newurl))


@dataclass(slots=True)
class ParsedEvent:
    uid: str
    title: str
    description: str | None
    start: datetime
    end: datetime | None
    all_day: bool


@dataclass(slots=True)
class ParsedFeed:
    name: str | None
    events: list[ParsedEvent]


def normalize_feed_url(raw: str) -> str:
    """Turn a pasted link into an https(s) iCal address."""
    text = raw.strip().strip("<>\"'").replace("\\n", "").replace("\n", "")
    lowered = text.lower()
    if lowered.startswith("webcal://"):
        text = "https://" + text[len("webcal://") :]
    elif lowered.startswith("webcals://"):
        text = "https://" + text[len("webcals://") :]
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise FeedError("Потрібне посилання, яке починається з https:// або webcal://")
    if "calendar.google.com" in parsed.hostname.lower():
        cid = urllib.parse.parse_qs(parsed.query).get("cid", [None])[0]
        if cid:
            text = _google_public_ics(cid)
            parsed = urllib.parse.urlparse(text)
    if parsed.port not in _PUBLIC_PORTS:
        raise FeedError("Дозволені лише звичайні посилання без окремого порту")
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def _google_public_ics(cid: str) -> str:
    padded = cid + "=" * (-len(cid) % 4)
    try:
        calendar_id = base64.urlsafe_b64decode(padded).decode().strip()
    except (ValueError, UnicodeDecodeError) as exc:
        raise FeedError("Не вдалося прочитати посилання Google Calendar") from exc
    if not calendar_id or any(char.isspace() for char in calendar_id):
        raise FeedError("Не вдалося прочитати посилання Google Calendar")
    quoted = urllib.parse.quote(calendar_id, safe="")
    return f"https://calendar.google.com/calendar/ical/{quoted}/public/basic.ics"


def assert_public_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme not in ("http", "https") or not host:
        raise FeedError("Потрібне посилання, яке починається з https:// або webcal://")
    if parsed.port not in _PUBLIC_PORTS:
        raise FeedError("Дозволені лише звичайні посилання без окремого порту")
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".local") or host.endswith(".internal"):
        raise FeedError("Це посилання веде у внутрішню мережу")
    if host.isdigit():
        raise FeedError("Це посилання веде у внутрішню мережу")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    addresses = [literal] if literal is not None else _resolve(host)
    if not addresses or any(not address.is_global for address in addresses):
        raise FeedError("Це посилання веде у внутрішню мережу")


def _resolve(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise FeedError("Не вдалося знайти адресу календаря") from exc
    found: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            found.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    return found


def download_ics(url: str) -> bytes:
    opener = urllib.request.build_opener(_StopRedirect)
    current = url
    for _ in range(5):
        assert_public_url(current)
        request = urllib.request.Request(
            current,
            headers={"User-Agent": "PlanerCalendar/1.0", "Accept": "text/calendar, text/plain, */*"},
            method="GET",
        )
        try:
            with opener.open(request, timeout=12) as response:
                chunks: list[bytes] = []
                total = 0
                while True:
                    block = response.read(65_536)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_BYTES:
                        raise FeedError("Файл календаря завеликий")
                    chunks.append(block)
                body = b"".join(chunks)
        except _Redirect as exc:
            current = urllib.parse.urljoin(current, exc.url)
            continue
        except FeedError:
            raise
        except urllib.error.HTTPError as exc:
            raise FeedError(f"Календар відповів помилкою {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise FeedError("Не вдалося відкрити посилання") from exc
        if not body.strip():
            raise FeedError("За посиланням порожній календар")
        return body
    raise FeedError("Забагато переадресацій")


def parse_ics(payload: bytes, *, now: datetime | None = None) -> ParsedFeed:
    try:
        calendar = Calendar.from_ical(payload)
    except Exception as exc:
        raise FeedError("Це не календар у форматі iCal") from exc
    if isinstance(calendar, list):
        calendar = next((item for item in calendar if hasattr(item, "walk")), None)
    if calendar is None or not hasattr(calendar, "walk"):
        raise FeedError("Це не календар у форматі iCal")
    current = now or datetime.now(TIMEZONE)
    window_start = current - PAST
    window_end = current + FUTURE
    try:
        instances = list(recurring_ical_events.of(calendar).between(window_start, window_end))
    except Exception:
        logger.warning("Could not expand recurring events", exc_info=True)
        instances = [event for event in calendar.walk("VEVENT") if not event.get("RRULE")]
    events: list[ParsedEvent] = []
    for event in instances:
        events.extend(_expand_event(event, window_start, window_end))
        if len(events) >= MAX_EVENTS:
            break
    events.sort(key=lambda item: item.start)
    raw_name = calendar.get("X-WR-CALNAME") if hasattr(calendar, "get") else None
    name = str(raw_name).strip()[:120] if raw_name else None
    return ParsedFeed(name=name or None, events=events[:MAX_EVENTS])


def _expand_event(event, window_start: datetime, window_end: datetime) -> list[ParsedEvent]:
    bounds = _bounds(event)
    if bounds is None:
        return []
    start, end, all_day = bounds
    title = str(event.get("SUMMARY") or "Подія").strip()[:255] or "Подія"
    description = str(event.get("DESCRIPTION") or "").strip() or None
    if description:
        description = description[:2000]
    base_uid = str(event.get("UID") or f"{title}-{start.isoformat()}")[:600]
    recurrence = event.get("RECURRENCE-ID")
    if recurrence is not None:
        base_uid = f"{base_uid}#{recurrence.dt}"[:700]
    if not all_day:
        if end <= window_start or start >= window_end:
            return []
        return [ParsedEvent(base_uid[:700], title, description, start, end, False)]

    last = (end or start + timedelta(days=1)).date()
    cursor = start.date()
    if last <= cursor:
        last = cursor + timedelta(days=1)
    found: list[ParsedEvent] = []
    spanned = 0
    while cursor < last and spanned < MAX_ALL_DAY_SPAN:
        day_start = datetime.combine(cursor, time.min, tzinfo=TIMEZONE)
        day_end = day_start + timedelta(days=1)
        spanned += 1
        cursor += timedelta(days=1)
        if day_end <= window_start or day_start >= window_end:
            continue
        found.append(
            ParsedEvent(
                uid=f"{base_uid}#{day_start.date().isoformat()}"[:700],
                title=title,
                description=description,
                start=day_start,
                end=day_end,
                all_day=True,
            )
        )
    return found


def _bounds(event) -> tuple[datetime, datetime, bool] | None:
    start_prop = event.get("DTSTART")
    if start_prop is None:
        return None
    start_raw = start_prop.dt
    end_prop = event.get("DTEND")
    end_raw = end_prop.dt if end_prop is not None else None
    if isinstance(start_raw, datetime):
        start = _as_vienna(start_raw)
        if isinstance(end_raw, datetime):
            end = _as_vienna(end_raw)
        else:
            end = start + timedelta(hours=1)
        if end <= start:
            end = start + timedelta(hours=1)
        return start, end, False
    if isinstance(start_raw, date):
        start = datetime.combine(start_raw, time.min, tzinfo=TIMEZONE)
        if isinstance(end_raw, date) and not isinstance(end_raw, datetime):
            end = datetime.combine(end_raw, time.min, tzinfo=TIMEZONE)
        else:
            end = start + timedelta(days=1)
        if end <= start:
            end = start + timedelta(days=1)
        return start, end, True
    return None


def _as_vienna(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE)


def feed_host(url: str) -> str:
    return urllib.parse.urlparse(url).hostname or "календар"


def stored_event_uids(events: list[ParsedEvent]) -> list[tuple[ParsedEvent, str]]:
    """One stable key per occurrence. Recurring copies share a UID, so the start is part of the key."""
    seen: set[str] = set()
    chosen: list[tuple[ParsedEvent, str]] = []
    for event in events:
        stamp = event.start.isoformat()
        uid = f"{event.uid[:700 - len(stamp) - 1]}#{stamp}"
        if uid in seen:
            continue
        seen.add(uid)
        chosen.append((event, uid))
    return chosen


def _as_task(event: ExternalEvent, feed: ExternalCalendar) -> TaskRead:
    return TaskRead(
        id=-event.id,
        title=event.title,
        description=event.description,
        category=None,
        priority=Priority.MEDIUM,
        deadline=event.end_time or event.start_time,
        remind_at=None,
        start_time=event.start_time,
        end_time=event.end_time,
        google_event_id=None,
        sync_token=None,
        is_completed=event.is_completed,
        is_shared=False,
        owner_id=feed.user_id,
        created_at=feed.last_sync_at or event.start_time,
        read_only=True,
        all_day=event.all_day,
        source_name=feed.name,
    )


async def list_feeds(session: AsyncSession, user_id: int) -> list[FeedRead]:
    feeds = list(
        await session.scalars(
            select(ExternalCalendar).where(ExternalCalendar.user_id == user_id).order_by(ExternalCalendar.id)
        )
    )
    if not feeds:
        return []
    counts = dict(
        (
            await session.execute(
                select(ExternalEvent.calendar_id, func.count())
                .where(ExternalEvent.calendar_id.in_([feed.id for feed in feeds]))
                .group_by(ExternalEvent.calendar_id)
            )
        ).all()
    )
    return [
        FeedRead(
            id=feed.id,
            name=feed.name,
            host=feed_host(feed.url),
            last_sync_at=feed.last_sync_at,
            last_error=feed.last_error,
            event_count=int(counts.get(feed.id, 0)),
        )
        for feed in feeds
    ]


async def add_feed(session: AsyncSession, user_id: int, url: str, name: str | None) -> ExternalCalendar:
    normalized = normalize_feed_url(url)
    existing = await session.scalar(
        select(ExternalCalendar).where(ExternalCalendar.user_id == user_id, ExternalCalendar.url == normalized)
    )
    if existing is None:
        count = await session.scalar(
            select(func.count()).select_from(ExternalCalendar).where(ExternalCalendar.user_id == user_id)
        )
        if int(count or 0) >= MAX_FEEDS:
            raise FeedError(f"Можна підключити не більше {MAX_FEEDS} календарів")
    try:
        payload = await asyncio.to_thread(download_ics, normalized)
        parsed = parse_ics(payload)
    except FeedError:
        raise
    except Exception as exc:
        logger.exception("External calendar fetch failed")
        raise FeedError("Не вдалося прочитати календар") from exc

    chosen = (name or "").strip() or parsed.name or feed_host(normalized)
    if existing is None:
        existing = ExternalCalendar(user_id=user_id, name=chosen[:120], url=normalized)
        session.add(existing)
        await session.flush()
    elif name and name.strip():
        existing.name = name.strip()[:120]
    elif not existing.name:
        existing.name = chosen[:120]
    await _replace_events(session, existing.id, parsed.events)
    existing.last_sync_at = datetime.now(TIMEZONE)
    existing.last_error = None
    await session.commit()
    await session.refresh(existing)
    return existing


async def delete_feed(session: AsyncSession, user_id: int, feed_id: int) -> bool:
    feed = await session.get(ExternalCalendar, feed_id)
    if feed is None or feed.user_id != user_id:
        return False
    await session.execute(delete(ExternalEvent).where(ExternalEvent.calendar_id == feed.id))
    await session.delete(feed)
    await session.commit()
    return True


async def events_for(session: AsyncSession, user_id: int, scope: TaskScope) -> list[TaskRead]:
    rows = (
        await session.execute(
            select(ExternalEvent, ExternalCalendar)
            .join(ExternalCalendar, ExternalCalendar.id == ExternalEvent.calendar_id)
            .where(ExternalCalendar.user_id == user_id)
            .order_by(ExternalEvent.start_time)
        )
    ).all()
    today_start = datetime.combine(datetime.now(TIMEZONE).date(), time.min, tzinfo=TIMEZONE)
    tomorrow = today_start + timedelta(days=1)
    reads: list[TaskRead] = []
    for event, feed in rows:
        if scope is TaskScope.TODAY and not (today_start <= event.start_time < tomorrow):
            continue
        if scope is TaskScope.UPCOMING and event.start_time < tomorrow:
            continue
        reads.append(_as_task(event, feed))
    return reads


async def set_event_completed(
    session: AsyncSession, user_id: int, event_id: int, completed: bool
) -> TaskRead | None:
    row = (
        await session.execute(
            select(ExternalEvent, ExternalCalendar)
            .join(ExternalCalendar, ExternalCalendar.id == ExternalEvent.calendar_id)
            .where(ExternalEvent.id == event_id, ExternalCalendar.user_id == user_id)
        )
    ).one_or_none()
    if row is None:
        return None
    event, feed = row
    event.is_completed = completed
    await session.commit()
    await session.refresh(event)
    return _as_task(event, feed)


async def _replace_events(session: AsyncSession, calendar_id: int, events: list[ParsedEvent]) -> None:
    # The feed is rewritten in full. Completion is local, so copy it onto the same occurrence.
    previous = dict(
        (
            await session.execute(
                select(ExternalEvent.uid, ExternalEvent.is_completed).where(ExternalEvent.calendar_id == calendar_id)
            )
        ).all()
    )
    await session.execute(delete(ExternalEvent).where(ExternalEvent.calendar_id == calendar_id))
    await session.flush()
    for event, uid in stored_event_uids(events):
        session.add(
            ExternalEvent(
                calendar_id=calendar_id,
                uid=uid,
                title=event.title,
                description=event.description,
                start_time=event.start,
                end_time=event.end,
                all_day=event.all_day,
                is_completed=bool(previous.get(uid)),
            )
        )


async def refresh_external_feeds() -> None:
    async with session_factory() as session:
        ids = list(await session.scalars(select(ExternalCalendar.id)))
    for feed_id in ids:
        try:
            await _refresh_one(feed_id)
        except Exception:
            logger.exception("External calendar %s refresh failed", feed_id)


async def _refresh_one(feed_id: int) -> None:
    async with session_factory() as session:
        feed = await session.get(ExternalCalendar, feed_id)
        if feed is None:
            return
        try:
            payload = await asyncio.to_thread(download_ics, feed.url)
            parsed = parse_ics(payload)
        except Exception as exc:
            feed.last_error = str(exc)[:500]
            await session.commit()
            logger.warning("External calendar %s did not refresh: %s", feed_id, exc)
            return
        await _replace_events(session, feed.id, parsed.events)
        feed.last_sync_at = datetime.now(TIMEZONE)
        feed.last_error = None
        await session.commit()

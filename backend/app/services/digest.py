"""Morning digest: today's tasks, overdue ones and habit streaks, sent once a day per user."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TIMEZONE
from app.models import (
    AuthIdentity,
    AuthProvider,
    NotificationPrefs,
    Priority,
    Space,
    SpaceKind,
    Task,
    TaskStatus,
    User,
)
from app.services import users as users_service

DEFAULT_DIGEST_TIME = time(8, 0)
# After downtime a missed digest is still sent, but not later than this.
CATCH_UP = timedelta(hours=2)
MAX_LINES = 10


@dataclass(frozen=True, slots=True)
class DigestItem:
    title: str
    when: datetime | None
    priority: Priority
    space: str | None = None  # None for the personal space
    streak: int | None = None
    recurring: bool = False


@dataclass(slots=True)
class DigestData:
    first_name: str
    today: list[DigestItem] = field(default_factory=list)
    overdue: list[DigestItem] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.today and not self.overdue


def user_zone(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return TIMEZONE


def is_due(prefs: NotificationPrefs | None, now_local: datetime) -> bool:
    """Whether the digest should go out now (in the user's local time)."""
    enabled = prefs.digest_enabled if prefs is not None else True
    if not enabled:
        return False
    if prefs is not None and prefs.last_digest_on == now_local.date():
        return False
    send_at = datetime.combine(
        now_local.date(),
        prefs.digest_time if prefs is not None else DEFAULT_DIGEST_TIME,
        tzinfo=now_local.tzinfo,
    )
    return send_at <= now_local < send_at + CATCH_UP


def _item_line(item: DigestItem, zone: ZoneInfo, *, with_day: bool) -> str:
    parts: list[str] = []
    if item.when is not None:
        local = item.when.astimezone(zone)
        date_only = local.hour == 23 and local.minute == 59
        if with_day:
            parts.append(f"<b>{local:%d.%m}</b>" if date_only else f"<b>{local:%d.%m %H:%M}</b>")
        elif not date_only:
            parts.append(f"<b>{local:%H:%M}</b>")
    title = escape(item.title)
    if item.priority is Priority.HIGH:
        title = f"🔺 {title}"
    parts.append(title)
    meta: list[str] = []
    if item.space:
        meta.append(f"📂 {escape(item.space)}")
    if item.streak:
        meta.append(f"🔥 {item.streak}")
    elif item.recurring:
        meta.append("🔁")
    line = " ".join(parts)
    return f"• {line}" + (f" · {' · '.join(meta)}" if meta else "")


def _section(title: str, items: list[DigestItem], zone: ZoneInfo, *, with_day: bool) -> list[str]:
    lines = [title]
    lines += [_item_line(item, zone, with_day=with_day) for item in items[:MAX_LINES]]
    if len(items) > MAX_LINES:
        lines.append(f"…і ще {len(items) - MAX_LINES}")
    return lines


def render_digest(data: DigestData, zone: ZoneInfo = TIMEZONE) -> str | None:
    """Telegram HTML text, or None when there is nothing to report."""
    if data.is_empty:
        return None
    hello = f"☀️ Доброго ранку, {escape(data.first_name)}!" if data.first_name else "☀️ Доброго ранку!"
    blocks = [hello]
    if data.today:
        blocks.append("\n".join(_section(f"📋 <b>Сьогодні · {len(data.today)}</b>", data.today, zone, with_day=False)))
    else:
        blocks.append("📋 На сьогодні запланованого немає.")
    if data.overdue:
        blocks.append(
            "\n".join(_section(f"⚠️ <b>Прострочені · {len(data.overdue)}</b>", data.overdue, zone, with_day=True))
        )
    streaks = [item for item in data.today if item.streak]
    if streaks:
        best = max(streaks, key=lambda item: item.streak or 0)
        blocks.append(f"🔥 Не перервай серію: <b>{escape(best.title)}</b> — {best.streak} поспіль")
    return "\n\n".join(blocks)


def _sort_key(task: Task) -> tuple:
    stamp = task.start_time or task.deadline
    weight = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}[task.priority]
    return (stamp is None, stamp or datetime.max.replace(tzinfo=TIMEZONE), weight)


async def collect_digest(session: AsyncSession, user: User, now_local: datetime) -> DigestData:
    zone = now_local.tzinfo or TIMEZONE
    start = datetime.combine(now_local.date(), time.min, tzinfo=zone)
    end = start + timedelta(days=1)
    rows = await session.execute(
        select(Task, Space)
        .join(Space, Space.id == Task.space_id)
        .where(
            Task.space_id.in_(users_service.member_space_ids(user.id)),
            Task.deleted_at.is_(None),
            Task.status != TaskStatus.DONE,
            Task.status != TaskStatus.BACKLOG,
            or_(Task.deadline < end, Task.start_time < end),
        )
    )
    data = DigestData(first_name=user.display_name.split(" ")[0] if user.display_name else "")
    for task, space in sorted(rows.all(), key=lambda row: _sort_key(row[0])):
        stamp = task.start_time or task.deadline
        if stamp is None:
            continue
        item = DigestItem(
            title=task.title,
            when=stamp,
            priority=task.priority,
            space=None if space.kind is SpaceKind.PERSONAL else space.name,
            streak=task.streak_current or None,
            recurring=task.recurrence_id is not None,
        )
        (data.today if stamp >= start else data.overdue).append(item)
    return data


@dataclass(frozen=True, slots=True)
class Recipient:
    user: User
    chat_id: int
    prefs: NotificationPrefs | None


async def recipients(session: AsyncSession) -> list[Recipient]:
    rows = await session.execute(
        select(User, AuthIdentity.external_id, NotificationPrefs)
        .join(AuthIdentity, AuthIdentity.user_id == User.id)
        .outerjoin(NotificationPrefs, NotificationPrefs.user_id == User.id)
        .where(
            AuthIdentity.provider == AuthProvider.TELEGRAM,
            AuthIdentity.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
    )
    return [Recipient(user=user, chat_id=int(chat), prefs=prefs) for user, chat, prefs in rows.all()]


async def get_prefs(session: AsyncSession, user_id: int) -> NotificationPrefs:
    prefs = await session.get(NotificationPrefs, user_id)
    if prefs is None:
        prefs = NotificationPrefs(user_id=user_id, digest_enabled=True, digest_time=DEFAULT_DIGEST_TIME)
        session.add(prefs)
        await session.flush()
    return prefs


async def mark_sent(session: AsyncSession, user_id: int, day: date) -> None:
    prefs = await get_prefs(session, user_id)
    prefs.last_digest_on = day
    await session.commit()

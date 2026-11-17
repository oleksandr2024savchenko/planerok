"""Reminders set relative to the event ("за день до", "за 2 години до")."""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta

from app.config import TIMEZONE

# Upper bound for an offset: four weeks before the event.
MAX_OFFSET_MINUTES = 4 * 7 * 24 * 60

# Date-only tasks (deadline 23:59) have no clock time, so "за день до" counts from 07:00 of that day.
# Same hour as imported all-day Google events, so an offset survives the Google round trip unchanged.
DATE_ONLY_ANCHOR = time(7, 0)
_END_OF_DAY = time(23, 59)

# Presets shown in the bot keyboard, in minutes.
PRESET_OFFSETS: tuple[int, ...] = (0, 15, 60, 3 * 60, 24 * 60, 2 * 24 * 60, 7 * 24 * 60)


def reminder_anchor(start_time: datetime | None, deadline: datetime | None) -> datetime | None:
    """The moment the offset counts back from: event start, timed deadline, or 07:00 on the due day."""
    if start_time is not None:
        return start_time.astimezone(TIMEZONE)
    if deadline is None:
        return None
    local = deadline.astimezone(TIMEZONE)
    if local.time().replace(second=0, microsecond=0) == _END_OF_DAY:
        return datetime.combine(local.date(), DATE_ONLY_ANCHOR, tzinfo=TIMEZONE)
    return local


def remind_at_for(
    start_time: datetime | None,
    deadline: datetime | None,
    offset_minutes: int | None,
) -> datetime | None:
    if offset_minutes is None:
        return None
    anchor = reminder_anchor(start_time, deadline)
    if anchor is None:
        return None
    return anchor - timedelta(minutes=offset_minutes)


def _plural(value: int, one: str, few: str, many: str) -> str:
    if value % 10 == 1 and value % 100 != 11:
        return one
    if value % 10 in (2, 3, 4) and value % 100 not in (12, 13, 14):
        return few
    return many


def format_offset(minutes: int) -> str:
    """Human Ukrainian label: 0 → «у момент події», 1440 → «за 1 день»."""
    if minutes <= 0:
        return "у момент події"
    week, day, hour = 7 * 24 * 60, 24 * 60, 60
    if minutes % week == 0:
        n = minutes // week
        return f"за {n} {_plural(n, 'тиждень', 'тижні', 'тижнів')}"
    if minutes % day == 0:
        n = minutes // day
        return f"за {n} {_plural(n, 'день', 'дні', 'днів')}"
    if minutes % hour == 0:
        n = minutes // hour
        return f"за {n} {_plural(n, 'годину', 'години', 'годин')}"
    return f"за {minutes} хв"


_UNIT_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"^(?:хв|min|m$)"), 1),
    (re.compile(r"^(?:год|h$|hour)"), 60),
    (re.compile(r"^(?:д(?:ень|ні|нів|ня|н)|доб|d$|day)"), 24 * 60),
    (re.compile(r"^(?:тиж|w$|week)"), 7 * 24 * 60),
)
_OFFSET_TEXT_RE = re.compile(r"^\s*(?:за\s+)?(\d{1,4})?\s*([^\d\s.,]+)?\.?(?:\s+до(?:\s+події)?)?\s*$", re.IGNORECASE)


def unit_minutes(unit: str) -> int | None:
    unit = unit.strip().lower()
    for pattern, minutes in _UNIT_PATTERNS:
        if pattern.match(unit):
            return minutes
    return None


def parse_offset(text: str) -> int | None:
    """«45 хв», «за 2 години», «день», «1 тиждень до» → minutes. A bare number means minutes."""
    match = _OFFSET_TEXT_RE.match(text)
    if match is None:
        return None
    count_raw, unit = match.groups()
    if count_raw is None and unit is None:
        return None
    count = int(count_raw) if count_raw is not None else 1
    per_unit = unit_minutes(unit) if unit is not None else 1
    if per_unit is None:
        return None
    minutes = count * per_unit
    return minutes if 0 <= minutes <= MAX_OFFSET_MINUTES else None


# --- "Додовбувач": repeat reminders for high-priority tasks until they are done -------------


def nag_settings() -> tuple[timedelta, time, time, timedelta]:
    from app.config import get_settings

    settings = get_settings()
    return (
        timedelta(minutes=max(settings.nag_interval_minutes, 1)),
        time(settings.nag_quiet_start_hour % 24),
        time(settings.nag_quiet_end_hour % 24),
        timedelta(days=settings.nag_give_up_days),
    )


def skip_quiet_hours(at: datetime, quiet_start: time, quiet_end: time) -> datetime:
    """Move a nag that would land at night to the end of the quiet window."""
    local = at.astimezone(TIMEZONE)
    clock = local.time()
    if quiet_start == quiet_end:
        return local
    if quiet_start > quiet_end:  # window crosses midnight, e.g. 23:00–08:00
        if clock >= quiet_start:
            return datetime.combine(local.date() + timedelta(days=1), quiet_end, tzinfo=TIMEZONE)
        if clock < quiet_end:
            return datetime.combine(local.date(), quiet_end, tzinfo=TIMEZONE)
        return local
    if quiet_start <= clock < quiet_end:
        return datetime.combine(local.date(), quiet_end, tzinfo=TIMEZONE)
    return local


def _nags(task) -> bool:
    from app.models import Priority

    return task.priority == Priority.HIGH and not task.is_completed


def next_nag_at(task, now: datetime) -> datetime | None:
    """When to nag again about a high-priority task whose reminder has already gone off."""
    if not _nags(task):
        return None
    interval, quiet_start, quiet_end, give_up = nag_settings()
    started = reminder_anchor(task.start_time, task.deadline) or task.remind_at
    if started is None:
        return None
    candidate = skip_quiet_hours(now + interval, quiet_start, quiet_end)
    if candidate > started + give_up:
        return None
    return candidate


def next_fire_at(task, now: datetime) -> datetime | None:
    """The next moment the bot should write about this task, or None."""
    if task.is_completed:
        return None
    if task.remind_at is not None and task.remind_at > now:
        return task.remind_at
    if not _nags(task):
        return None
    if task.remind_at is not None:
        first = task.remind_at
    else:
        anchor = reminder_anchor(task.start_time, task.deadline)
        if anchor is None:
            return None
        # No reminder was set by hand, so the nagging start also respects the night.
        _, quiet_start, quiet_end, _ = nag_settings()
        first = skip_quiet_hours(anchor, quiet_start, quiet_end)
    if first > now:
        return first
    return next_nag_at(task, now)

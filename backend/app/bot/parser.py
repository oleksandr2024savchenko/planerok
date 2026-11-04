"""Parses free-form chat messages into tasks.

Example: "Здати звіт завтра о 10:00 #робота !!!"
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.config import TIMEZONE
from app.models import Priority

_CATEGORY_RE = re.compile(r"(?<!\w)#(\w+)")
_PRIORITY_RE = re.compile(r"(?<!\S)!(high|medium|low|!{0,2})(?!\S)", re.IGNORECASE)
_TIME_RE = re.compile(r"(?:(?<!\w)(?:о|об|в|на|at)\s+)?(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])", re.IGNORECASE)
_DATE_RE = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})(?:\.(\d{2}|\d{4}))?(?![\d.])")
_RELATIVE_DAYS = {"сьогодні": 0, "завтра": 1, "післязавтра": 2}
_RELATIVE_RE = re.compile(r"(?<!\w)(" + "|".join(_RELATIVE_DAYS) + r")(?!\w)", re.IGNORECASE)

_PRIORITY_TOKENS = {
    "": Priority.LOW,
    "!": Priority.MEDIUM,
    "!!": Priority.HIGH,
    "low": Priority.LOW,
    "medium": Priority.MEDIUM,
    "high": Priority.HIGH,
}

END_OF_DAY = time(23, 59)


@dataclass(slots=True)
class ParsedTask:
    title: str
    description: str | None = None
    category: str | None = None
    priority: Priority = Priority.MEDIUM
    deadline: datetime | None = None
    remind_at: datetime | None = None


class EmptyTitleError(ValueError):
    pass


def parse_task(text: str, now: datetime | None = None) -> ParsedTask:
    now = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE)
    first_line, _, rest = text.strip().partition("\n")
    line = first_line

    category: str | None = None
    if match := _CATEGORY_RE.search(line):
        category = match.group(1).lower()
    line = _CATEGORY_RE.sub(" ", line)

    priority = Priority.MEDIUM
    if match := _PRIORITY_RE.search(line):
        priority = _PRIORITY_TOKENS[match.group(1).lower()]
        line = line[: match.start()] + " " + line[match.end() :]

    day: date | None = None
    if match := _RELATIVE_RE.search(line):
        day = now.date() + timedelta(days=_RELATIVE_DAYS[match.group(1).lower()])
        line = line[: match.start()] + " " + line[match.end() :]
    elif match := _DATE_RE.search(line):
        day = _parse_date(match, now.date())
        if day is not None:
            line = line[: match.start()] + " " + line[match.end() :]

    at: time | None = None
    if match := _TIME_RE.search(line):
        at = time(int(match.group(1)), int(match.group(2)))
        line = line[: match.start()] + " " + line[match.end() :]

    title = re.sub(r"\s+", " ", line).strip(" ,.-")
    if not title:
        raise EmptyTitleError("Task title is empty")

    deadline: datetime | None = None
    remind_at: datetime | None = None
    if at is not None:
        target_day = day or now.date()
        deadline = datetime.combine(target_day, at, tzinfo=TIMEZONE)
        if day is None and deadline <= now:
            deadline += timedelta(days=1)
        remind_at = deadline
    elif day is not None:
        deadline = datetime.combine(day, END_OF_DAY, tzinfo=TIMEZONE)

    return ParsedTask(
        title=title[:255],
        description=rest.strip() or None,
        category=category,
        priority=priority,
        deadline=deadline,
        remind_at=remind_at,
    )


def _parse_date(match: re.Match[str], today: date) -> date | None:
    day_num, month_num, year_raw = int(match.group(1)), int(match.group(2)), match.group(3)
    year = today.year
    if year_raw:
        year = int(year_raw) + (2000 if len(year_raw) == 2 else 0)
    try:
        parsed = date(year, month_num, day_num)
    except ValueError:
        return None
    if not year_raw and parsed < today:
        parsed = parsed.replace(year=year + 1)
    return parsed

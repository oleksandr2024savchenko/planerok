"""Parses free-form chat messages into tasks.

Example: "Здати звіт завтра о 10:00 #робота !!!" or "Звіт #Бізнес !high @пт"
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.config import TIMEZONE
from app.models import Priority
from app.services.recurrence import first_occurrence, next_occurrence, parse_rule

_CATEGORY_RE = re.compile(r"(?<!\w)#(\w+)")
_PRIORITY_RE = re.compile(r"(?<!\S)!(high|medium|low|!{0,2})(?!\S)", re.IGNORECASE)
_TIME_RE = re.compile(r"(?:(?<!\w)(?:о|об|в|на|at)\s+)?(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])", re.IGNORECASE)
_DATE_RE = re.compile(r"(?<![\d.])@?(\d{1,2})\.(\d{1,2})(?:\.(\d{2}|\d{4}))?(?![\d.])")
_RELATIVE_DAYS = {"сьогодні": 0, "завтра": 1, "післязавтра": 2}
_RELATIVE_RE = re.compile(r"(?<!\w)@?(" + "|".join(_RELATIVE_DAYS) + r")(?!\w)", re.IGNORECASE)
_APOSTROPHE = "['’ʼ]?"
_WEEKDAY_NAMES: tuple[tuple[str, str], ...] = (
    ("пн", "понеділок"),
    ("вт", "вівторок"),
    ("ср", "серед[аую]"),
    ("чт", "четвер"),
    ("пт", f"п{_APOSTROPHE}ятниц[яюі]"),
    ("сб", "субот[аиу]"),
    ("нд", "неділ[яюі]"),
)
_RECURRENCE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"щодня|щоденно|@щодня", "FREQ=DAILY"),
    (r"по\s+буднях|@будні", "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"),
    (r"щотижня|@щотижня", "FREQ=WEEKLY"),
    (r"щомісяця|@щомісяця", "FREQ=MONTHLY"),
    (r"щопонеділка|@щопн", "FREQ=WEEKLY;BYDAY=MO"),
    (r"щовівторка|@щовт", "FREQ=WEEKLY;BYDAY=TU"),
    (r"щосереди|@щоср", "FREQ=WEEKLY;BYDAY=WE"),
    (r"щочетверга|@щочт", "FREQ=WEEKLY;BYDAY=TH"),
    (rf"щоп{_APOSTROPHE}ятниці|@щопт", "FREQ=WEEKLY;BYDAY=FR"),
    (r"щосуботи|@щосб", "FREQ=WEEKLY;BYDAY=SA"),
    (r"щонеділі|@щонд", "FREQ=WEEKLY;BYDAY=SU"),
)
_RECURRENCE_RES = tuple(
    (re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", re.IGNORECASE), rule) for pattern, rule in _RECURRENCE_PATTERNS
)
# Full names work with or without "@"; two-letter forms only after "@" ("@пт").
_WEEKDAY_RES = tuple(
    re.compile(rf"(?<!\w)(?:@(?:{short}|{full})|(?:(?:у|в|до|на)\s+)?(?:{full}))(?!\w)", re.IGNORECASE)
    for short, full in _WEEKDAY_NAMES
)

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
    recurrence: str | None = None


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

    recurrence: str | None = None
    for pattern, rule in _RECURRENCE_RES:
        if match := pattern.search(line):
            recurrence = rule
            line = line[: match.start()] + " " + line[match.end() :]
            break

    day: date | None = None
    if match := _RELATIVE_RE.search(line):
        day = now.date() + timedelta(days=_RELATIVE_DAYS[match.group(1).lower()])
        line = line[: match.start()] + " " + line[match.end() :]
    elif match := _DATE_RE.search(line):
        day = _parse_date(match, now.date())
        if day is not None:
            line = line[: match.start()] + " " + line[match.end() :]
    else:
        for weekday, pattern in enumerate(_WEEKDAY_RES):
            if match := pattern.search(line):
                # Same weekday as today means today.
                day = now.date() + timedelta(days=(weekday - now.weekday()) % 7)
                line = line[: match.start()] + " " + line[match.end() :]
                break

    at: time | None = None
    if match := _TIME_RE.search(line):
        at = time(int(match.group(1)), int(match.group(2)))
        line = line[: match.start()] + " " + line[match.end() :]

    if recurrence is not None and day is None:
        rule = parse_rule(recurrence)
        day = first_occurrence(rule, now.date())
        if at is not None and datetime.combine(day, at, tzinfo=TIMEZONE) <= now:
            day = next_occurrence(rule, day, day)

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
        recurrence=recurrence,
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


def normalize_tag(value: str) -> str:
    """"Бізнес", "#бізнес" and "Мій Бізнес" → comparable tag keys."""
    return re.sub(r"[\s_\-#]+", "", value).lower()


def split_tags(text: str) -> list[str]:
    """Raw #tags of the first line, in order."""
    first_line = text.strip().partition("\n")[0]
    return [match.group(1) for match in _CATEGORY_RE.finditer(first_line)]


def remove_tag(text: str, tag: str) -> str:
    pattern = re.compile(rf"(?<!\w)#{re.escape(tag)}(?!\w)")
    first_line, sep, rest = text.strip().partition("\n")
    first_line = re.sub(r"\s{2,}", " ", pattern.sub(" ", first_line, count=1)).strip()
    return first_line + sep + rest

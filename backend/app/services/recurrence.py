"""Recurring tasks: a small RRULE subset, next occurrence and streaks. Pure functions only.

Supported rules (RFC 5545 syntax):
    FREQ=DAILY[;INTERVAL=n]
    FREQ=WEEKLY[;INTERVAL=n][;BYDAY=MO,TU,...]
    FREQ=MONTHLY[;INTERVAL=n][;BYMONTHDAY=d]
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum

from app.config import TIMEZONE

WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
MAX_INTERVAL = 365


class Freq(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class InvalidRuleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Rule:
    freq: Freq
    interval: int = 1
    by_day: tuple[int, ...] = field(default_factory=tuple)  # 0 = Monday
    by_month_day: int | None = None

    def __str__(self) -> str:
        parts = [f"FREQ={self.freq.value}"]
        if self.interval != 1:
            parts.append(f"INTERVAL={self.interval}")
        if self.by_day:
            parts.append("BYDAY=" + ",".join(WEEKDAY_CODES[d] for d in self.by_day))
        if self.by_month_day is not None:
            parts.append(f"BYMONTHDAY={self.by_month_day}")
        return ";".join(parts)


def parse_rule(raw: str) -> Rule:
    text = raw.strip().upper().removeprefix("RRULE:")
    try:
        pairs = dict(part.split("=", 1) for part in text.split(";") if part)
    except ValueError as exc:
        raise InvalidRuleError(raw) from exc
    unknown = set(pairs) - {"FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY"}
    if unknown:
        raise InvalidRuleError(f"Unsupported RRULE parts: {sorted(unknown)}")
    try:
        freq = Freq(pairs.get("FREQ", ""))
        interval = int(pairs.get("INTERVAL", "1"))
        by_day = tuple(sorted({WEEKDAY_CODES.index(code) for code in pairs["BYDAY"].split(",")})) if "BYDAY" in pairs else ()
        by_month_day = int(pairs["BYMONTHDAY"]) if "BYMONTHDAY" in pairs else None
    except ValueError as exc:
        raise InvalidRuleError(raw) from exc
    if not 1 <= interval <= MAX_INTERVAL:
        raise InvalidRuleError("INTERVAL out of range")
    if by_day and freq is not Freq.WEEKLY:
        raise InvalidRuleError("BYDAY is supported only for WEEKLY")
    if by_month_day is not None and (freq is not Freq.MONTHLY or not 1 <= by_month_day <= 31):
        raise InvalidRuleError("BYMONTHDAY is supported only for MONTHLY, 1..31")
    return Rule(freq=freq, interval=interval, by_day=by_day, by_month_day=by_month_day)


def normalize_rule(raw: str | None) -> str | None:
    """Validates and canonicalizes a rule; None/blank stays None."""
    if raw is None or not raw.strip():
        return None
    return str(parse_rule(raw))


def _add_months(day: date, months: int, month_day: int) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(month_day, calendar.monthrange(year, month)[1]))


def _matches(rule: Rule, anchor: date, day: date) -> bool:
    if rule.freq is Freq.DAILY:
        return (day - anchor).days % rule.interval == 0
    if rule.freq is Freq.WEEKLY:
        weekdays = rule.by_day or (anchor.weekday(),)
        anchor_week = anchor - timedelta(days=anchor.weekday())
        week = day - timedelta(days=day.weekday())
        return day.weekday() in weekdays and ((week - anchor_week).days // 7) % rule.interval == 0
    raise AssertionError("monthly is handled separately")


def next_occurrence(rule: Rule, anchor: date, after: date) -> date:
    """First day strictly after `after` that the rule hits, counting intervals from `anchor`."""
    if rule.freq is Freq.MONTHLY:
        month_day = rule.by_month_day or anchor.day
        months = 0
        while True:
            candidate = _add_months(anchor, months, month_day)
            if candidate > after:
                return candidate
            months += rule.interval
    day = after + timedelta(days=1)
    for _ in range(7 * rule.interval + 1):
        if day >= anchor and _matches(rule, anchor, day):
            return day
        day += timedelta(days=1)
    raise AssertionError("rule never matches")  # unreachable for validated rules


def first_occurrence(rule: Rule, on_or_after: date) -> date:
    """First due day for a new series that starts on `on_or_after`."""
    if rule.freq is Freq.WEEKLY and rule.by_day and on_or_after.weekday() not in rule.by_day:
        return next_occurrence(rule, on_or_after, on_or_after)
    if rule.freq is Freq.MONTHLY and rule.by_month_day is not None and on_or_after.day != rule.by_month_day:
        return next_occurrence(rule, on_or_after.replace(day=1), on_or_after - timedelta(days=1))
    return on_or_after


@dataclass(frozen=True, slots=True)
class Shift:
    """How far to move every datetime of the task to reach the next occurrence."""

    due_day: date
    delta: timedelta


def plan_next(rule: Rule, anchor: date, due: datetime, completed_at: datetime) -> Shift:
    """Next occurrence after completing the one due at `due`.

    Missed occurrences are skipped: the next one is after both the due day and today.
    """
    due_local = due.astimezone(TIMEZONE)
    today = completed_at.astimezone(TIMEZONE).date()
    next_day = next_occurrence(rule, anchor, max(due_local.date(), today))
    next_due = datetime.combine(next_day, due_local.time(), tzinfo=TIMEZONE)
    # Wall-clock time stays the same across DST changes.
    return Shift(due_day=next_day, delta=next_due - due_local)


def is_on_time(due: datetime, completed_at: datetime) -> bool:
    """Done on time = completed no later than the end of the due day (local time)."""
    end_of_day = datetime.combine(due.astimezone(TIMEZONE).date(), time.max, tzinfo=TIMEZONE)
    return completed_at <= end_of_day


def update_streak(current: int, best: int, on_time: bool) -> tuple[int, int]:
    current = current + 1 if on_time else 1
    return current, max(best, current)


_WEEKDAY_LABELS = ("пн", "вт", "ср", "чт", "пт", "сб", "нд")


def describe(raw: str) -> str:
    """Ukrainian label for the UI and the bot."""
    rule = parse_rule(raw)
    if rule.freq is Freq.DAILY:
        return "щодня" if rule.interval == 1 else f"кожні {rule.interval} дн."
    if rule.freq is Freq.WEEKLY:
        if rule.by_day == (0, 1, 2, 3, 4) and rule.interval == 1:
            return "по буднях"
        days = ", ".join(_WEEKDAY_LABELS[d] for d in rule.by_day)
        base = "щотижня" if rule.interval == 1 else f"кожні {rule.interval} тиж."
        return f"{base} ({days})" if days else base
    base = "щомісяця" if rule.interval == 1 else f"кожні {rule.interval} міс."
    return f"{base}, {rule.by_month_day}-го" if rule.by_month_day else base

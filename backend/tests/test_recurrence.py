from datetime import date, datetime

import pytest

from app.config import TIMEZONE
from app.services.recurrence import (
    InvalidRuleError,
    describe,
    first_occurrence,
    is_on_time,
    next_occurrence,
    normalize_rule,
    parse_rule,
    plan_next,
    update_streak,
)

TUE = date(2026, 11, 3)


def test_rule_roundtrip_and_validation() -> None:
    assert normalize_rule("rrule:freq=weekly;byday=fr,mo") == "FREQ=WEEKLY;BYDAY=MO,FR"
    assert normalize_rule("FREQ=DAILY;INTERVAL=1") == "FREQ=DAILY"
    assert normalize_rule("  ") is None
    for bad in ("FREQ=YEARLY", "FREQ=DAILY;BYDAY=MO", "FREQ=MONTHLY;BYMONTHDAY=32", "FREQ=DAILY;COUNT=3", "junk"):
        with pytest.raises(InvalidRuleError):
            parse_rule(bad)


@pytest.mark.parametrize(
    ("rule", "after", "expected"),
    [
        ("FREQ=DAILY", TUE, date(2026, 11, 4)),
        ("FREQ=DAILY;INTERVAL=3", date(2026, 11, 4), date(2026, 11, 6)),
        ("FREQ=WEEKLY", TUE, date(2026, 11, 10)),
        ("FREQ=WEEKLY;BYDAY=MO,WE,FR", TUE, date(2026, 11, 4)),
        ("FREQ=WEEKLY;BYDAY=MO,WE,FR", date(2026, 11, 6), date(2026, 11, 9)),
        ("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO", TUE, date(2026, 11, 16)),
        ("FREQ=MONTHLY", TUE, date(2026, 12, 3)),
        ("FREQ=MONTHLY;BYMONTHDAY=31", date(2026, 11, 30), date(2026, 12, 31)),
        ("FREQ=MONTHLY;BYMONTHDAY=31", date(2027, 1, 31), date(2027, 2, 28)),
    ],
)
def test_next_occurrence(rule: str, after: date, expected: date) -> None:
    assert next_occurrence(parse_rule(rule), TUE, after) == expected


def test_first_occurrence() -> None:
    assert first_occurrence(parse_rule("FREQ=DAILY"), TUE) == TUE
    assert first_occurrence(parse_rule("FREQ=WEEKLY;BYDAY=FR"), TUE) == date(2026, 11, 6)
    assert first_occurrence(parse_rule("FREQ=WEEKLY;BYDAY=TU"), TUE) == TUE
    assert first_occurrence(parse_rule("FREQ=MONTHLY;BYMONTHDAY=1"), TUE) == date(2026, 12, 1)
    assert first_occurrence(parse_rule("FREQ=MONTHLY;BYMONTHDAY=20"), TUE) == date(2026, 11, 20)


def test_plan_next_keeps_time_and_skips_missed_days() -> None:
    rule = parse_rule("FREQ=DAILY")
    due = datetime(2026, 11, 3, 8, 0, tzinfo=TIMEZONE)

    on_time = plan_next(rule, TUE, due, completed_at=datetime(2026, 11, 3, 7, 50, tzinfo=TIMEZONE))
    assert on_time.due_day == date(2026, 11, 4)
    assert due + on_time.delta == datetime(2026, 11, 4, 8, 0, tzinfo=TIMEZONE)

    late = plan_next(rule, TUE, due, completed_at=datetime(2026, 11, 6, 21, 0, tzinfo=TIMEZONE))
    assert late.due_day == date(2026, 11, 7)


def test_plan_next_keeps_wall_clock_across_dst() -> None:
    due = datetime(2026, 10, 24, 8, 0, tzinfo=TIMEZONE)  # DST ends on 25.10
    shift = plan_next(parse_rule("FREQ=DAILY"), due.date(), due, completed_at=due)
    assert (due + shift.delta).astimezone(TIMEZONE).hour == 8


def test_streaks() -> None:
    due = datetime(2026, 11, 3, 8, 0, tzinfo=TIMEZONE)
    assert is_on_time(due, datetime(2026, 11, 3, 23, 30, tzinfo=TIMEZONE))
    assert not is_on_time(due, datetime(2026, 11, 4, 0, 5, tzinfo=TIMEZONE))
    assert update_streak(4, 4, on_time=True) == (5, 5)
    assert update_streak(5, 7, on_time=False) == (1, 7)


@pytest.mark.parametrize(
    ("rule", "label"),
    [
        ("FREQ=DAILY", "щодня"),
        ("FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", "по буднях"),
        ("FREQ=WEEKLY;BYDAY=MO", "щотижня (пн)"),
        ("FREQ=MONTHLY;BYMONTHDAY=5", "щомісяця, 5-го"),
        ("FREQ=DAILY;INTERVAL=2", "кожні 2 дн."),
    ],
)
def test_describe(rule: str, label: str) -> None:
    assert describe(rule) == label

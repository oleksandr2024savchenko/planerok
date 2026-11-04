from datetime import datetime, timedelta

from app.config import TIMEZONE
from app.models import Priority, Task
from app.services.google_calendar import (
    build_event_body,
    default_reminder,
    parse_google_event,
)

NOW = datetime(2026, 11, 4, 16, 0, tzinfo=TIMEZONE)


def test_parse_timed_event_keeps_vienna_range_and_task_link() -> None:
    change = parse_google_event(
        {
            "id": "evt-1",
            "summary": "Синк з клієнтом",
            "description": "Порядок денний",
            "start": {"dateTime": "2026-11-04T09:00:00Z"},
            "end": {"dateTime": "2026-11-04T10:30:00+01:00"},
            "extendedProperties": {"private": {"planerTaskId": "12"}},
        }
    )
    assert change is not None
    assert change.event_id == "evt-1"
    assert change.title == "Синк з клієнтом"
    assert change.description == "Порядок денний"
    assert change.start == datetime(2026, 11, 4, 10, 0, tzinfo=TIMEZONE)
    assert change.end == datetime(2026, 11, 4, 10, 30, tzinfo=TIMEZONE)
    assert change.planer_task_id == 12
    assert change.cancelled is False


def test_parse_all_day_event_becomes_morning_block() -> None:
    change = parse_google_event(
        {
            "id": "day-1",
            "summary": "Відпустка",
            "start": {"date": "2026-11-04"},
            "end": {"date": "2026-11-05"},
        }
    )
    assert change is not None
    assert change.start == datetime(2026, 11, 4, 7, 0, tzinfo=TIMEZONE)
    assert change.end == change.start + timedelta(hours=1)


def test_parse_cancelled_event() -> None:
    change = parse_google_event({"id": "evt-1", "status": "cancelled"})
    assert change is not None
    assert change.cancelled is True
    assert change.start is None


def test_parse_ignores_events_without_a_start() -> None:
    assert parse_google_event({"id": "evt-1", "summary": "Без часу"}) is None
    assert parse_google_event({"summary": "Без id"}) is None


def test_parse_ignores_non_numeric_task_link() -> None:
    change = parse_google_event(
        {
            "id": "evt-1",
            "summary": "Дзвінок",
            "start": {"dateTime": "2026-11-04T10:00:00+01:00"},
            "end": {"dateTime": "2026-11-04T11:00:00+01:00"},
            "extendedProperties": {"private": {"planerTaskId": "nope"}},
        }
    )
    assert change is not None
    assert change.planer_task_id is None


def test_default_reminder_is_fifteen_minutes_before_a_future_start() -> None:
    start = datetime(2026, 11, 4, 18, 0, tzinfo=TIMEZONE)
    assert default_reminder(start, now=NOW) == start - timedelta(minutes=15)


def test_default_reminder_uses_the_start_when_the_early_window_has_passed() -> None:
    start = datetime(2026, 11, 4, 16, 10, tzinfo=TIMEZONE)
    assert default_reminder(start, now=NOW) == start


def test_default_reminder_skips_events_that_already_started() -> None:
    start = datetime(2026, 11, 4, 15, 0, tzinfo=TIMEZONE)
    assert default_reminder(start, now=NOW) is None


def test_build_event_body_uses_explicit_block() -> None:
    start = datetime(2026, 11, 5, 10, 0, tzinfo=TIMEZONE)
    end = datetime(2026, 11, 5, 11, 30, tzinfo=TIMEZONE)
    task = Task(
        id=7,
        user_id=1,
        title="Зустріч",
        description="Нотатки",
        priority=Priority.MEDIUM,
        is_completed=False,
        start_time=start,
        end_time=end,
    )
    body = build_event_body(task)
    assert body is not None
    assert body["summary"] == "Зустріч"
    assert body["description"] == "Нотатки"
    assert body["start"]["timeZone"] == "Europe/Vienna"
    assert body["start"]["dateTime"].startswith("2026-11-05T10:00:00")
    assert body["end"]["dateTime"].startswith("2026-11-05T11:30:00")
    assert body["extendedProperties"]["private"]["planerTaskId"] == "7"


def test_build_event_body_turns_a_timed_deadline_into_one_hour() -> None:
    deadline = datetime(2026, 11, 5, 10, 0, tzinfo=TIMEZONE)
    task = Task(
        id=8,
        user_id=1,
        title="Дзвінок",
        priority=Priority.HIGH,
        is_completed=False,
        deadline=deadline,
    )
    body = build_event_body(task)
    assert body is not None
    assert body["start"]["dateTime"].startswith("2026-11-05T10:00:00")
    assert body["end"]["dateTime"].startswith("2026-11-05T11:00:00")


def test_build_event_body_skips_date_only_deadline() -> None:
    task = Task(
        id=9,
        user_id=1,
        title="Купити продукти",
        priority=Priority.LOW,
        is_completed=False,
        deadline=datetime(2026, 11, 5, 23, 59, tzinfo=TIMEZONE),
    )
    assert build_event_body(task) is None


def test_build_event_body_extends_an_end_that_is_not_after_the_start() -> None:
    start = datetime(2026, 11, 5, 10, 0, tzinfo=TIMEZONE)
    task = Task(
        id=10,
        user_id=1,
        title="Блок",
        priority=Priority.MEDIUM,
        is_completed=False,
        start_time=start,
        end_time=start,
    )
    body = build_event_body(task)
    assert body is not None
    assert body["end"]["dateTime"].startswith("2026-11-05T11:00:00")

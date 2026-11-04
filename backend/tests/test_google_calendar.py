from datetime import datetime, timedelta

from app.config import TIMEZONE
from app.models import Task
from app.services.google_calendar import (
    build_event_body,
    default_reminder,
    parse_google_event,
)
from app.services.tasks import apply_schedule

NOW = datetime(2026, 11, 4, 9, 0, tzinfo=TIMEZONE)


def test_event_body_uses_vienna_timezone() -> None:
    task = Task(
        id=7,
        user_id=1,
        title="Зал",
        description="Спина",
        start_time=datetime(2026, 11, 4, 18, 0, tzinfo=TIMEZONE),
        end_time=datetime(2026, 11, 4, 19, 0, tzinfo=TIMEZONE),
    )
    body = build_event_body(task)
    assert body is not None
    assert body["start"]["timeZone"] == "Europe/Vienna"
    assert body["end"]["timeZone"] == "Europe/Vienna"
    assert body["start"]["dateTime"].startswith("2026-11-04T18:00:00")
    assert body["extendedProperties"]["private"]["planerTaskId"] == "7"
    assert body["description"] == "Спина"


def test_date_only_deadline_is_not_a_calendar_block() -> None:
    task = Task(
        id=1,
        user_id=1,
        title="Оплатити рахунок",
        deadline=datetime(2026, 11, 4, 23, 59, tzinfo=TIMEZONE),
    )
    assert build_event_body(task) is None


def test_apply_schedule_fills_one_hour_and_skips_end_of_day() -> None:
    timed = datetime(2026, 11, 4, 10, 0, tzinfo=TIMEZONE)
    payload = apply_schedule({"deadline": timed, "start_time": None, "end_time": None})
    assert payload["start_time"] == timed
    assert payload["end_time"] == timed + timedelta(hours=1)

    end_of_day = datetime(2026, 11, 4, 23, 59, tzinfo=TIMEZONE)
    untouched = apply_schedule({"deadline": end_of_day, "start_time": None, "end_time": None})
    assert untouched["start_time"] is None


def test_parse_timed_and_all_day_events() -> None:
    timed = parse_google_event(
        {
            "id": "evt-1",
            "summary": "Стендап",
            "description": "Щоденний",
            "status": "confirmed",
            "start": {"dateTime": "2026-11-04T10:00:00+01:00"},
            "end": {"dateTime": "2026-11-04T10:30:00+01:00"},
            "extendedProperties": {"private": {"planerTaskId": "4"}},
        }
    )
    assert timed is not None
    assert timed.title == "Стендап"
    assert timed.planer_task_id == 4
    assert timed.start == datetime(2026, 11, 4, 10, 0, tzinfo=TIMEZONE)
    assert timed.end == datetime(2026, 11, 4, 10, 30, tzinfo=TIMEZONE)

    all_day = parse_google_event(
        {
            "id": "evt-2",
            "summary": "Відпустка",
            "start": {"date": "2026-11-06"},
            "end": {"date": "2026-11-07"},
        }
    )
    assert all_day is not None
    assert all_day.start == datetime(2026, 11, 6, 7, 0, tzinfo=TIMEZONE)
    assert all_day.end == datetime(2026, 11, 6, 8, 0, tzinfo=TIMEZONE)


def test_cancelled_event_and_default_reminder() -> None:
    cancelled = parse_google_event({"id": "evt-3", "status": "cancelled"})
    assert cancelled is not None and cancelled.cancelled

    start = datetime(2026, 11, 4, 18, 0, tzinfo=TIMEZONE)
    assert default_reminder(start, now=NOW) == start - timedelta(minutes=15)

    soon = datetime(2026, 11, 4, 9, 10, tzinfo=TIMEZONE)
    assert default_reminder(soon, now=NOW) == soon

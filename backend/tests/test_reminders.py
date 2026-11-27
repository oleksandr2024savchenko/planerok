from datetime import datetime, timedelta

import pytest

from app.bot.parser import parse_task
from app.config import TIMEZONE
from app.models import Task
from app.schemas import TaskCreate
from app.services.ai_agent import ParsedTask, finalize_task, to_task_create
from app.services.google_calendar import build_event_body, parse_google_event
from app.services.reminders import format_offset, parse_offset, remind_at_for, reminder_anchor
from app.services.tasks import apply_relative_reminder

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=TIMEZONE)
EVENT = datetime(2026, 11, 20, 18, 0, tzinfo=TIMEZONE)


def test_offset_counts_back_from_event_start() -> None:
    assert remind_at_for(EVENT, None, 24 * 60) == EVENT - timedelta(days=1)
    assert remind_at_for(None, EVENT, 0) == EVENT
    assert remind_at_for(None, None, 60) is None
    assert remind_at_for(EVENT, None, None) is None


def test_date_only_deadline_anchors_at_seven() -> None:
    end_of_day = datetime(2026, 11, 20, 23, 59, tzinfo=TIMEZONE)
    assert reminder_anchor(None, end_of_day) == datetime(2026, 11, 20, 7, 0, tzinfo=TIMEZONE)
    assert remind_at_for(None, end_of_day, 24 * 60) == datetime(2026, 11, 19, 7, 0, tzinfo=TIMEZONE)


@pytest.mark.parametrize(
    ("minutes", "label"),
    [
        (0, "у момент події"),
        (15, "за 15 хв"),
        (60, "за 1 годину"),
        (180, "за 3 години"),
        (24 * 60, "за 1 день"),
        (2 * 24 * 60, "за 2 дні"),
        (5 * 24 * 60, "за 5 днів"),
        (7 * 24 * 60, "за 1 тиждень"),
        (90, "за 90 хв"),
    ],
)
def test_format_offset(minutes: int, label: str) -> None:
    assert format_offset(minutes) == label


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("45 хв", 45),
        ("за 2 години", 120),
        ("день", 24 * 60),
        ("3 дні", 3 * 24 * 60),
        ("1 тиждень до події", 7 * 24 * 60),
        ("30", 30),
        ("2h", 120),
        ("щось", None),
        ("", None),
        ("9999 днів", None),
    ],
)
def test_parse_offset(text: str, minutes: int | None) -> None:
    assert parse_offset(text) == minutes


def _task(**kwargs) -> Task:
    return Task(id=1, user_id=1, title="Лікар", **kwargs)


def test_relative_reminder_follows_moved_event() -> None:
    task = _task(start_time=EVENT, deadline=EVENT + timedelta(hours=1), remind_before_minutes=60)
    apply_relative_reminder(task, explicit_remind_at=False, offset_changed=True, anchor_changed=True)
    assert task.remind_at == EVENT - timedelta(hours=1)

    task.start_time = EVENT + timedelta(days=1)
    apply_relative_reminder(task, explicit_remind_at=False, offset_changed=False, anchor_changed=True)
    assert task.remind_at == EVENT + timedelta(days=1) - timedelta(hours=1)


def test_explicit_remind_at_wins_over_offset() -> None:
    snoozed = NOW + timedelta(minutes=15)
    task = _task(start_time=EVENT, remind_before_minutes=60, remind_at=snoozed)
    apply_relative_reminder(task, explicit_remind_at=True, offset_changed=False, anchor_changed=False)
    assert task.remind_at == snoozed


def test_schema_rejects_negative_and_huge_offsets() -> None:
    with pytest.raises(ValueError):
        TaskCreate(title="x", remind_before_minutes=-5)
    with pytest.raises(ValueError):
        TaskCreate(title="x", remind_before_minutes=10**6)


def test_regex_parser_reads_remind_before() -> None:
    parsed = parse_task("Лікар 20.11 о 18:00 нагадай за день", now=NOW)
    assert parsed.title == "Лікар"
    assert parsed.deadline == EVENT
    assert parsed.remind_before_minutes == 24 * 60
    assert parsed.remind_at == EVENT - timedelta(days=1)

    hours = parse_task("Зустріч завтра о 10:00 нагадати за 2 години до", now=NOW)
    assert hours.title == "Зустріч"
    assert hours.remind_before_minutes == 120


def test_regex_parser_ignores_offset_without_date() -> None:
    parsed = parse_task("Купити подарунок нагадай за день", now=NOW)
    assert parsed.title == "Купити подарунок"
    assert parsed.remind_before_minutes is None
    assert parsed.remind_at is None


def test_ai_offset_overrides_default_reminder() -> None:
    task = finalize_task(
        ParsedTask(title="Лікар", category="personal", deadline=EVENT, remind_before_minutes=1440),
        now=NOW,
    )
    assert task.remind_at == EVENT - timedelta(days=1)
    create = to_task_create(task)
    assert create.remind_before_minutes == 1440
    assert create.remind_at is None


def test_ai_offset_is_clamped_and_blank_is_none() -> None:
    assert ParsedTask(title="a", category="personal", remind_before_minutes="").remind_before_minutes is None
    assert ParsedTask(title="a", category="personal", remind_before_minutes=10**7).remind_before_minutes == 40320


def test_event_body_carries_popup_override() -> None:
    task = _task(start_time=EVENT, end_time=EVENT + timedelta(hours=1), remind_before_minutes=1440)
    body = build_event_body(task)
    assert body is not None
    assert body["reminders"] == {"useDefault": False, "overrides": [{"method": "popup", "minutes": 1440}]}

    plain = build_event_body(_task(start_time=EVENT))
    assert plain is not None
    assert plain["reminders"] == {"useDefault": True}


def test_all_day_event_override_counts_from_midnight() -> None:
    task = _task(deadline=datetime(2026, 11, 20, 23, 59, tzinfo=TIMEZONE), remind_before_minutes=24 * 60)
    body = build_event_body(task)
    assert body is not None
    # Day before at 07:00 == 17 hours before midnight of the event day.
    minutes = body["reminders"]["overrides"][0]["minutes"]
    assert minutes == 17 * 60

    echoed = parse_google_event(
        {
            "id": "evt",
            "summary": task.title,
            "start": body["start"],
            "end": body["end"],
            "reminders": body["reminders"],
        }
    )
    assert echoed is not None
    assert echoed.remind_before_minutes == 24 * 60


def test_google_reminder_overrides_are_imported() -> None:
    timed = parse_google_event(
        {
            "id": "evt",
            "summary": "Лікар",
            "start": {"dateTime": "2026-11-20T18:00:00+01:00"},
            "end": {"dateTime": "2026-11-20T19:00:00+01:00"},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "email", "minutes": 5}, {"method": "popup", "minutes": 30}],
            },
        }
    )
    assert timed is not None
    assert timed.remind_before_minutes == 30
    assert not timed.uses_default_reminders

    all_day = parse_google_event(
        {
            "id": "evt2",
            "summary": "ДН",
            "start": {"date": "2026-11-20"},
            "end": {"date": "2026-11-21"},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 0}]},
        }
    )
    assert all_day is not None
    # Imported block starts at 07:00, so "at midnight" becomes 7 hours before it.
    assert all_day.remind_before_minutes == 7 * 60

    default = parse_google_event(
        {
            "id": "evt3",
            "summary": "x",
            "start": {"dateTime": "2026-11-20T18:00:00+01:00"},
            "end": {"dateTime": "2026-11-20T19:00:00+01:00"},
            "reminders": {"useDefault": True},
        }
    )
    assert default is not None
    assert default.remind_before_minutes is None
    assert default.uses_default_reminders


def test_ics_events_serialize_without_reminder_offset() -> None:
    from app.models import ExternalCalendar, ExternalEvent
    from app.services.external_calendars import _as_task

    feed = ExternalCalendar(id=1, user_id=1, name="Універ", url="https://example.com/a.ics")
    event = ExternalEvent(
        id=5,
        calendar_id=1,
        uid="u#1",
        title="Лекція",
        start_time=EVENT,
        end_time=EVENT + timedelta(hours=1),
        all_day=False,
        is_completed=False,
    )
    read = _as_task(event, feed)
    assert read.id == -5
    assert read.remind_before_minutes is None
    assert read.model_dump(mode="json")["remind_before_minutes"] is None

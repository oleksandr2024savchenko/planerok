"""Timetable PDF import: weekly rows become dated events; duplicates and junk are dropped."""

import asyncio
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.config import TIMEZONE
from app.schemas import Assignee
from app.services import schedule_import as si
from app.services.ai_agent import TaskExtractionError

TODAY = date(2026, 11, 26)  # Thursday


def _x(*items, title=None) -> si.ScheduleExtraction:
    return si.ScheduleExtraction(title=title, items=[si.ScheduleItem(**i) for i in items])


def test_weekly_lesson_repeats_until_semester_end() -> None:
    events = si.expand(_x({"title": "Математика", "start": "10:00", "end": "11:30", "weekday": 1, "until": "2026-12-21"}), TODAY)
    assert [e.start.date().isoformat() for e in events] == ["2026-11-30", "2026-12-07", "2026-12-14", "2026-12-21"]
    assert events[0].start == datetime(2026, 11, 30, 10, 0, tzinfo=TIMEZONE)
    assert events[0].end == datetime(2026, 11, 30, 11, 30, tzinfo=TIMEZONE)


def test_today_counts_and_default_horizon_is_eight_weeks() -> None:
    events = si.expand(_x({"title": "Англійська", "start": "18:00", "weekday": 4}), TODAY)
    assert events[0].start.date() == TODAY
    assert len(events) == 9  # today + 8 weeks
    assert events[0].end == datetime(2026, 11, 26, 19, 30, tzinfo=TIMEZONE)  # no end → 90 min


def test_every_other_week_from_first_date() -> None:
    events = si.expand(
        _x({"title": "Фізика (знаменник)", "start": "08:30", "weekday": 3, "every_weeks": 2,
            "first_date": "2026-12-09", "until": "2027-01-20"}),
        TODAY,
    )
    assert [e.start.date().isoformat() for e in events] == ["2026-12-09", "2026-12-23", "2027-01-06", "2027-01-20"]


def test_one_off_dates_location_and_note() -> None:
    events = si.expand(
        _x({"title": "Екзамен", "start": "9.00", "date": "2026-12-18", "location": "ауд. 204", "note": "Іваненко"},
           {"title": "Минуле", "start": "10:00", "date": "2026-11-01"}),
        TODAY,
    )
    assert len(events) == 1
    assert events[0].start == datetime(2026, 12, 18, 9, 0, tzinfo=TIMEZONE)
    assert events[0].description == "ауд. 204 · Іваненко"


def test_junk_rows_and_duplicates_are_dropped() -> None:
    events = si.expand(
        _x({"title": "Без часу", "start": "колись", "weekday": 2},
           {"title": "", "start": "10:00", "weekday": 2},
           {"title": "Без дня", "start": "10:00"},
           {"title": "Хімія", "start": "12:00", "date": "2026-12-01"},
           {"title": "Хімія", "start": "12:00", "date": "2026-12-01"}),
        TODAY,
    )
    assert [e.title for e in events] == ["Хімія"]


def test_far_future_and_too_many_are_capped() -> None:
    rows = [{"title": f"Пара {n}", "start": f"{8 + n % 10:02d}:00", "weekday": 1 + n % 7, "until": "2028-01-01"} for n in range(40)]
    events = si.expand(_x(*rows), TODAY)
    assert len(events) == si.MAX_EVENTS
    assert max(e.start.date() for e in events) <= date(2027, 3, 18)  # 16 weeks


def test_not_a_pdf_is_refused_before_gemini() -> None:
    with pytest.raises(TaskExtractionError):
        asyncio.run(si.read_pdf(b"hello"))


def test_gemini_text_answer_is_parsed() -> None:
    response = SimpleNamespace(parsed=None, text='```json\n{"title":"КН-21","items":[{"title":"ООП","start":"10:00","weekday":5}]}\n```')
    assert si._coerce(response).items[0].title == "ООП"


def test_import_skips_events_already_in_the_planner(monkeypatch) -> None:
    from app.services import tasks as tasks_service

    made: list[dict] = []

    async def fake_create(session, user_id, data, **kw):
        made.append({"title": data.title, "assignee": data.assignee, "notify": kw.get("notify"), "google": kw.get("push_google")})
        return SimpleNamespace(id=len(made))

    async def fake_partner(session, user_id):
        return 2

    class _Session:
        def __init__(self):
            self.calls = 0

        async def scalar(self, _stmt):
            self.calls += 1
            return 99 if self.calls == 1 else None  # the first one already exists

    monkeypatch.setattr(tasks_service, "create_task", fake_create)
    monkeypatch.setattr(tasks_service, "_partner_of", fake_partner)
    events = si.expand(_x({"title": "Йога", "start": "19:00", "weekday": 1, "until": "2026-12-14"}), TODAY)
    created, skipped = asyncio.run(
        si.import_occurrences(_Session(), 1, events, assignee=Assignee.SHARED, category="тренування", remind_before_minutes=15)
    )
    assert skipped == 1 and len(created) == len(events) - 1
    assert all(m["assignee"] is Assignee.SHARED and m["notify"] is False and m["google"] is False for m in made)

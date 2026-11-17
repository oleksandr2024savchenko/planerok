"""«Додовбувач»: high-priority tasks are re-sent until done."""

import asyncio
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

from app import scheduler as sched
from app.bot.texts import reminder_text
from app.config import TIMEZONE
from app.models import Priority, Task
from app.services.reminders import next_fire_at, next_nag_at, skip_quiet_hours

NOW = datetime(2026, 11, 17, 15, 0, tzinfo=TIMEZONE)
EVENT = datetime(2026, 11, 17, 14, 0, tzinfo=TIMEZONE)
Q_START, Q_END = time(23, 0), time(8, 0)


def _task(**kwargs) -> Task:
    base = dict(id=7, user_id=1, owner_id=1, title="Здати звіт", priority=Priority.HIGH, is_completed=False)
    base.update(kwargs)
    return Task(**base)


def test_quiet_hours_push_night_nags_to_morning() -> None:
    late = datetime(2026, 11, 17, 23, 30, tzinfo=TIMEZONE)
    early = datetime(2026, 11, 18, 6, 0, tzinfo=TIMEZONE)
    day = datetime(2026, 11, 18, 12, 0, tzinfo=TIMEZONE)
    morning = datetime(2026, 11, 18, 8, 0, tzinfo=TIMEZONE)
    assert skip_quiet_hours(late, Q_START, Q_END) == morning
    assert skip_quiet_hours(early, Q_START, Q_END) == morning
    assert skip_quiet_hours(day, Q_START, Q_END) == day


def test_high_task_nags_every_interval_after_its_reminder() -> None:
    task = _task(start_time=EVENT, remind_at=EVENT - timedelta(minutes=15))
    assert next_fire_at(task, NOW) == NOW + timedelta(minutes=5)
    assert next_nag_at(task, NOW) == NOW + timedelta(minutes=5)


def test_future_reminder_comes_first() -> None:
    remind = NOW + timedelta(hours=2)
    task = _task(start_time=NOW + timedelta(hours=3), remind_at=remind)
    assert next_fire_at(task, NOW) == remind


def test_only_high_priority_nags() -> None:
    task = _task(priority=Priority.MEDIUM, start_time=EVENT, remind_at=EVENT)
    assert next_fire_at(task, NOW) is None
    assert next_nag_at(task, NOW) is None


def test_done_task_stops_nagging() -> None:
    task = _task(start_time=EVENT, remind_at=EVENT, is_completed=True)
    assert next_fire_at(task, NOW) is None


def test_nagging_gives_up_days_after_the_event() -> None:
    task = _task(start_time=EVENT, remind_at=EVENT)
    assert next_fire_at(task, EVENT + timedelta(days=2)) is not None
    assert next_fire_at(task, EVENT + timedelta(days=3, minutes=1)) is None


def test_high_task_without_reminder_starts_at_event_but_not_at_night() -> None:
    timed = _task(start_time=NOW + timedelta(hours=1))
    assert next_fire_at(timed, NOW) == NOW + timedelta(hours=1)
    # Date-only deadline counts from 07:00, which is still quiet time: start at 08:00.
    tomorrow = _task(deadline=datetime(2026, 11, 18, 23, 59, tzinfo=TIMEZONE))
    assert next_fire_at(tomorrow, NOW) == datetime(2026, 11, 18, 8, 0, tzinfo=TIMEZONE)


def test_task_without_any_time_never_nags() -> None:
    assert next_fire_at(_task(), NOW) is None


def test_nag_text() -> None:
    task = _task(start_time=EVENT, category=None, description=None)
    assert "Додовбувач" in reminder_text(task, nag_count=2, nagging=True)
    assert "3-й раз" in reminder_text(task, nag_count=2, nagging=True)
    assert "кожні 5 хв" in reminder_text(task, nagging=True)
    assert "Нагадування" in reminder_text(task)


class _FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.deleted: list[tuple[int, int]] = []
        self._next_id = 100

    async def send_message(self, chat_id: int, text: str, reply_markup=None):
        self._next_id += 1
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=self._next_id)

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))


class _FakeSession:
    def __init__(self, task: Task | None) -> None:
        self.task = task

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def get(self, _model, _id):
        return self.task


@pytest.fixture
def fire(monkeypatch):
    bot = _FakeBot()
    scheduled: list[dict] = []
    monkeypatch.setattr(sched, "_bot", bot)
    monkeypatch.setattr(
        sched,
        "schedule_reminder",
        lambda task_id, run_at, **kw: scheduled.append({"task_id": task_id, "run_at": run_at, **kw}),
    )

    def run(task: Task | None, **kwargs):
        monkeypatch.setattr(sched, "session_factory", lambda: _FakeSession(task))
        asyncio.run(sched.send_reminder(7, **kwargs))
        return bot, scheduled

    return run


def test_send_reminder_chains_nags_and_cleans_up(fire) -> None:
    task = _task(start_time=datetime.now(TIMEZONE) - timedelta(minutes=1), remind_at=datetime.now(TIMEZONE))
    bot, scheduled = fire(task, previous={1: 55}, nag_count=1)
    assert bot.deleted == [(1, 55)]
    assert len(bot.sent) == 1 and "2-й раз" in bot.sent[0][1]
    assert scheduled[0]["nag_count"] == 2
    assert scheduled[0]["previous"] == {1: 101}


def test_send_reminder_for_medium_task_does_not_chain(fire) -> None:
    task = _task(priority=Priority.MEDIUM, start_time=datetime.now(TIMEZONE), remind_at=datetime.now(TIMEZONE))
    bot, scheduled = fire(task)
    assert len(bot.sent) == 1 and "Додовбувач" not in bot.sent[0][1]
    assert scheduled == []


def test_done_task_only_removes_the_last_nag(fire) -> None:
    task = _task(start_time=datetime.now(TIMEZONE), remind_at=datetime.now(TIMEZONE), is_completed=True)
    bot, scheduled = fire(task, previous={1: 77})
    assert bot.deleted == [(1, 77)]
    assert bot.sent == [] and scheduled == []

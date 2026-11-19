"""Focus timer: start, pause, resume, stop, finish — with a controllable clock."""

import asyncio
from datetime import datetime, timedelta

import pytest

from app import scheduler
from app.config import TIMEZONE
from app.models import Priority, Task, TaskTimer
from app.services import timers

T0 = datetime(2026, 11, 19, 10, 0, tzinfo=TIMEZONE)


class _Session:
    def __init__(self, task: Task) -> None:
        self.task = task
        self.timers: dict[int, TaskTimer] = {}

    def add(self, obj) -> None:
        obj.id = len(self.timers) + 1
        self.timers[obj.id] = obj

    async def commit(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None

    async def get(self, model, key):
        return self.task if model is Task else self.timers.get(key)

    async def scalar(self, _stmt):
        live = [t for t in self.timers.values() if t.status in timers.LIVE]
        return live[-1] if live else None


@pytest.fixture
def env(monkeypatch):
    clock = {"now": T0}
    jobs: dict[int, datetime | None] = {}
    monkeypatch.setattr(timers, "now", lambda: clock["now"])
    monkeypatch.setattr(scheduler, "schedule_timer", lambda tid, ts: jobs.__setitem__(tid, datetime.fromtimestamp(ts, TIMEZONE)))
    monkeypatch.setattr(scheduler, "cancel_timer", lambda tid: jobs.__setitem__(tid, None))
    task = Task(id=5, user_id=1, owner_id=1, title="Вчити німецьку", priority=Priority.MEDIUM, focused_seconds=0)
    session = _Session(task)

    def tick(minutes: float) -> None:
        clock["now"] += timedelta(minutes=minutes)

    return session, task, jobs, tick


def run(coro):
    return asyncio.run(coro)


def test_twenty_minutes_with_a_pause(env) -> None:
    session, task, jobs, tick = env
    timer = run(timers.start(session, 1, task, 20))
    assert jobs[timer.id] == T0 + timedelta(minutes=20)

    tick(8)
    run(timers.pause(session, timer))
    assert timer.status == "paused" and timer.elapsed_seconds == 8 * 60 and jobs[timer.id] is None

    tick(30)  # a long break while paused does not count
    assert timers.remaining(timer, timers.now()) == 12 * 60
    run(timers.resume(session, timer))
    assert jobs[timer.id] == timers.now() + timedelta(minutes=12)

    tick(12)
    finished = run(timers.finish(session, timer.id))
    assert finished is timer and timer.status == "done"
    assert task.focused_seconds == 20 * 60


def test_stop_credits_only_the_time_spent(env) -> None:
    session, task, _jobs, tick = env
    timer = run(timers.start(session, 1, task, 40))
    tick(15)
    run(timers.stop(session, timer))
    assert timer.status == "stopped" and task.focused_seconds == 15 * 60


def test_break_does_not_count_as_focus(env) -> None:
    session, task, _jobs, tick = env
    timer = run(timers.start(session, 1, task, 5, kind=timers.BREAK))
    tick(5)
    run(timers.finish(session, timer.id))
    assert timer.status == "done" and task.focused_seconds == 0


def test_starting_again_closes_the_running_one(env) -> None:
    session, task, _jobs, tick = env
    first = run(timers.start(session, 1, task, 20))
    tick(10)
    second = run(timers.start(session, 1, task, 40))
    assert first.status == "stopped" and second.status == "running"
    assert task.focused_seconds == 10 * 60


def test_early_job_reschedules_instead_of_finishing(env) -> None:
    session, task, jobs, tick = env
    timer = run(timers.start(session, 1, task, 20))
    tick(5)
    run(timers.pause(session, timer))
    run(timers.resume(session, timer))
    assert run(timers.finish(session, timer.id)) is None  # 15 min still left
    assert timer.status == "running" and jobs[timer.id] == timers.now() + timedelta(minutes=15)


def test_paused_timer_is_not_finished_by_a_stale_job(env) -> None:
    session, task, _jobs, tick = env
    timer = run(timers.start(session, 1, task, 20))
    tick(3)
    run(timers.pause(session, timer))
    tick(30)
    assert run(timers.finish(session, timer.id)) is None
    assert timer.status == "paused"


def test_minutes_are_clamped(env) -> None:
    session, task, _jobs, _tick = env
    assert run(timers.start(session, 1, task, 0)).duration_seconds == 60
    assert run(timers.start(session, 1, task, 10_000)).duration_seconds == timers.MAX_MINUTES * 60


def test_minutes_label() -> None:
    from app.bot.texts import format_minutes

    assert format_minutes(20 * 60) == "20 хв"
    assert format_minutes(65 * 60) == "1 год 05 хв"
    assert format_minutes(120 * 60) == "2 год"

"""Focus timers: run, pause, resume, stop, and finish on time even with the Mini App closed."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TIMEZONE
from app.models import Task, TaskTimer

logger = logging.getLogger(__name__)

FOCUS, BREAK = "focus", "break"
RUNNING, PAUSED, DONE, STOPPED = "running", "paused", "done", "stopped"
LIVE = (RUNNING, PAUSED)
MAX_MINUTES = 8 * 60


def now() -> datetime:
    return datetime.now(TIMEZONE)


def elapsed(timer: TaskTimer, at: datetime) -> int:
    live = int((at - timer.running_since).total_seconds()) if timer.running_since else 0
    return min(timer.duration_seconds, timer.elapsed_seconds + max(live, 0))


def remaining(timer: TaskTimer, at: datetime) -> int:
    return max(timer.duration_seconds - elapsed(timer, at), 0)


async def active_timer(session: AsyncSession, user_id: int) -> TaskTimer | None:
    return await session.scalar(
        select(TaskTimer)
        .where(TaskTimer.user_id == user_id, TaskTimer.status.in_(LIVE))
        .order_by(TaskTimer.id.desc())
        .limit(1)
    )


async def _close(session: AsyncSession, timer: TaskTimer, status: str, at: datetime) -> None:
    """Freeze the clock, credit focus time to the task, and drop the end-of-session job."""
    from app import scheduler

    spent = elapsed(timer, at)
    timer.elapsed_seconds = spent
    timer.running_since = None
    timer.status = status
    timer.finished_at = at
    if timer.kind == FOCUS and spent > 0:
        task = await session.get(Task, timer.task_id)
        if task is not None:
            task.focused_seconds = (task.focused_seconds or 0) + spent
    scheduler.cancel_timer(timer.id)


async def start(session: AsyncSession, user_id: int, task: Task, minutes: int, kind: str = FOCUS) -> TaskTimer:
    from app import scheduler

    at = now()
    current = await active_timer(session, user_id)
    if current is not None:
        await _close(session, current, STOPPED, at)
    minutes = max(1, min(int(minutes), MAX_MINUTES))
    timer = TaskTimer(
        user_id=user_id,
        task_id=task.id,
        kind=kind,
        status=RUNNING,
        duration_seconds=minutes * 60,
        elapsed_seconds=0,
        running_since=at,
    )
    session.add(timer)
    await session.commit()
    await session.refresh(timer)
    scheduler.schedule_timer(timer.id, at.timestamp() + timer.duration_seconds)
    return timer


async def pause(session: AsyncSession, timer: TaskTimer) -> TaskTimer:
    from app import scheduler

    if timer.status == RUNNING:
        at = now()
        timer.elapsed_seconds = elapsed(timer, at)
        timer.running_since = None
        timer.status = PAUSED
        await session.commit()
        scheduler.cancel_timer(timer.id)
    return timer


async def resume(session: AsyncSession, timer: TaskTimer) -> TaskTimer:
    from app import scheduler

    if timer.status == PAUSED:
        at = now()
        timer.running_since = at
        timer.status = RUNNING
        await session.commit()
        scheduler.schedule_timer(timer.id, at.timestamp() + remaining(timer, at))
    return timer


async def stop(session: AsyncSession, timer: TaskTimer) -> TaskTimer:
    if timer.status in LIVE:
        await _close(session, timer, STOPPED, now())
        await session.commit()
    return timer


async def finish(session: AsyncSession, timer_id: int) -> TaskTimer | None:
    """Called by the scheduler when the time is up. Returns the timer if it really just ended."""
    timer = await session.get(TaskTimer, timer_id)
    if timer is None or timer.status != RUNNING:
        return None
    at = now()
    if remaining(timer, at) > 2:
        # Resumed later than the job thought (clock drift, restart): try again at the real end.
        from app import scheduler

        scheduler.schedule_timer(timer.id, at.timestamp() + remaining(timer, at))
        return None
    await _close(session, timer, DONE, at)
    await session.commit()
    return timer

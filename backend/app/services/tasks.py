import logging
from collections.abc import Sequence
from datetime import datetime, time, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scheduler
from app.config import TIMEZONE
from app.models import Task
from app.schemas import TaskCreate, TaskScope, TaskUpdate

logger = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now(TIMEZONE)


def _day_bounds(day_offset: int = 0) -> tuple[datetime, datetime]:
    start = datetime.combine(now().date() + timedelta(days=day_offset), time.min, tzinfo=TIMEZONE)
    return start, start + timedelta(days=1)


def sync_reminder(task: Task) -> None:
    if task.is_completed or task.remind_at is None or task.remind_at <= now():
        scheduler.cancel_reminder(task.id)
    else:
        scheduler.schedule_reminder(task.id, task.remind_at)


def _on_day(column, start: datetime, end: datetime):
    return and_(column.is_not(None), column >= start, column < end)


def apply_schedule(payload: dict) -> dict:
    """Fill a one-hour block when the task has a real clock time, not an end-of-day date."""
    start = payload.get("start_time")
    deadline = payload.get("deadline")
    if start is None and deadline is not None:
        local = deadline.astimezone(TIMEZONE)
        if not (local.hour == 23 and local.minute == 59):
            start = deadline
            payload["start_time"] = start
    if start is not None and payload.get("end_time") is None:
        payload["end_time"] = start + timedelta(hours=1)
    if payload.get("deadline") is None and payload.get("end_time") is not None:
        payload["deadline"] = payload["end_time"]
    return payload


async def list_tasks(
    session: AsyncSession,
    user_id: int,
    scope: TaskScope = TaskScope.ALL,
    category: str | None = None,
) -> Sequence[Task]:
    stmt = select(Task).where(Task.user_id == user_id)

    today_start, tomorrow_start = _day_bounds()
    if scope is TaskScope.TODAY:
        stmt = stmt.where(
            or_(
                _on_day(Task.deadline, today_start, tomorrow_start),
                _on_day(Task.start_time, today_start, tomorrow_start),
                and_(Task.deadline.is_not(None), Task.deadline < today_start, Task.is_completed.is_(False)),
            )
        )
    elif scope is TaskScope.UPCOMING:
        stmt = stmt.where(or_(Task.deadline >= tomorrow_start, Task.start_time >= tomorrow_start))

    if category:
        stmt = stmt.where(Task.category == category)

    stmt = stmt.order_by(
        Task.is_completed,
        Task.deadline.asc().nulls_last(),
        Task.created_at.desc(),
    )
    result = await session.scalars(stmt)
    return result.all()


async def get_task(session: AsyncSession, user_id: int, task_id: int) -> Task | None:
    task = await session.get(Task, task_id)
    if task is None or task.user_id != user_id:
        return None
    return task


async def create_task(
    session: AsyncSession,
    user_id: int,
    data: TaskCreate,
    *,
    push_google: bool = True,
) -> Task:
    task = Task(user_id=user_id, **apply_schedule(data.model_dump()))
    session.add(task)
    await session.commit()
    await session.refresh(task)
    sync_reminder(task)
    if push_google:
        await _mirror_google(session, task)
    return task


async def update_task(
    session: AsyncSession,
    task: Task,
    data: TaskUpdate,
    *,
    push_google: bool = True,
) -> Task:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    if task.start_time is not None and task.end_time is None:
        task.end_time = task.start_time + timedelta(hours=1)
    await session.commit()
    await session.refresh(task)
    sync_reminder(task)
    if push_google:
        await _mirror_google(session, task)
    return task


async def delete_task(session: AsyncSession, task: Task, *, push_google: bool = True) -> None:
    task_id = task.id
    event_id = task.google_event_id
    await session.delete(task)
    await session.commit()
    scheduler.cancel_reminder(task_id)
    if push_google and event_id:
        from app.services.google_calendar import delete_google_event

        await delete_google_event(event_id)


async def _mirror_google(session: AsyncSession, task: Task) -> None:
    from app.services.google_calendar import (
        GoogleCalendarError,
        create_google_event,
        delete_google_event,
        is_configured,
        update_google_event,
    )

    if not is_configured():
        return
    has_block = task.start_time is not None or task.end_time is not None
    try:
        if task.google_event_id and not has_block:
            await delete_google_event(task.google_event_id)
            task.google_event_id = None
            await session.commit()
            return
        if not has_block:
            return
        if task.google_event_id:
            await update_google_event(task)
        else:
            task.google_event_id = await create_google_event(task)
        await session.commit()
    except GoogleCalendarError:
        logger.warning("Google Calendar mirror failed for task %s", task.id, exc_info=True)


async def complete_task(session: AsyncSession, task: Task) -> Task:
    return await update_task(session, task, TaskUpdate(is_completed=True))


async def snooze_task(session: AsyncSession, task: Task, delta: timedelta) -> Task:
    return await update_task(session, task, TaskUpdate(remind_at=now() + delta))


async def postpone_to_tomorrow(session: AsyncSession, task: Task) -> Task:
    """Moves reminder (and deadline, if any) to tomorrow, keeping the time of day."""
    tomorrow = now().date() + timedelta(days=1)
    base = task.remind_at or task.deadline
    reminder_time = base.astimezone(TIMEZONE).time() if base else time(9, 0)
    changes: dict[str, datetime] = {
        "remind_at": datetime.combine(tomorrow, reminder_time, tzinfo=TIMEZONE),
    }
    if task.deadline is not None:
        deadline_time = task.deadline.astimezone(TIMEZONE).time()
        changes["deadline"] = datetime.combine(tomorrow, deadline_time, tzinfo=TIMEZONE)
    return await update_task(session, task, TaskUpdate(**changes))

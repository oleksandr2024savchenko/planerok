import logging
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scheduler
from app.config import TIMEZONE
from app.models import Recurrence, Task, TaskStatus
from app.schemas import TaskCreate, TaskScope, TaskUpdate
from app.services import recurrence as recurrence_rules
from app.services import users as users_service

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
    space_id: int | None = None,
    status: TaskStatus | None = None,
) -> Sequence[Task]:
    stmt = select(Task).where(
        Task.space_id.in_(users_service.member_space_ids(user_id)),
        Task.deleted_at.is_(None),
    )
    if space_id is not None:
        stmt = stmt.where(Task.space_id == space_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)

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


class SpaceAccessError(PermissionError):
    pass


async def get_task(session: AsyncSession, user_id: int, task_id: int, *, write: bool = False) -> Task | None:
    """Returns the task only if the user is a member of its space (with write access when asked)."""
    task = await session.get(Task, task_id)
    if task is None or task.deleted_at is not None:
        return None
    role = await users_service.get_role(session, user_id, task.space_id)
    if role is None or (write and role not in users_service.WRITE_ROLES):
        return None
    return task


END_OF_DAY = time(23, 59)


def _due_for_rule(rule: str, deadline: datetime | None) -> datetime:
    """A recurring task always has a due date; default to the first matching day."""
    if deadline is not None:
        return deadline
    day = recurrence_rules.first_occurrence(recurrence_rules.parse_rule(rule), now().date())
    return datetime.combine(day, END_OF_DAY, tzinfo=TIMEZONE)


async def _attach_recurrence(session: AsyncSession, task: Task, rule: str | None) -> None:
    """Starts, changes or stops (rule=None) the series of a task. Caller commits."""
    if rule is None:
        if task.recurrence is not None:
            task.recurrence.deleted_at = datetime.now(UTC)
            task.recurrence = None
        return
    task.deadline = _due_for_rule(rule, task.deadline)
    starts_on = task.deadline.astimezone(TIMEZONE).date()
    if task.recurrence is not None and task.recurrence.deleted_at is None:
        task.recurrence.rule = rule
        task.recurrence.starts_on = starts_on
        task.recurrence.space_id = task.space_id
        return
    task.recurrence = Recurrence(space_id=task.space_id, rule=rule, starts_on=starts_on)
    session.add(task.recurrence)


async def _finish(session: AsyncSession, task: Task, *, push_google: bool) -> None:
    await session.commit()
    await session.refresh(task)
    sync_reminder(task)
    if push_google:
        await _mirror_google(session, task)


async def create_task(
    session: AsyncSession,
    user_id: int,
    data: TaskCreate,
    *,
    push_google: bool = True,
) -> Task:
    payload = data.model_dump()
    space_id = payload.pop("space_id", None)
    rule = payload.pop("recurrence", None)
    if space_id is None:
        space_id = await users_service.personal_space_id(session, user_id)
    elif not await users_service.can_write(session, user_id, space_id):
        raise SpaceAccessError(f"User {user_id} cannot write to space {space_id}")
    payload["is_completed"] = payload["status"] is TaskStatus.DONE
    if rule is not None:
        payload["deadline"] = _due_for_rule(rule, payload.get("deadline"))
    task = Task(space_id=space_id, created_by_id=user_id, **apply_schedule(payload))
    session.add(task)
    await _attach_recurrence(session, task, rule)
    await _finish(session, task, push_google=push_google)
    return task


async def _on_completed(session: AsyncSession, task: Task, *, push_google: bool) -> None:
    """Counts the streak and schedules the next task of the series."""
    series = task.recurrence
    if series is None or series.deleted_at is not None or task.deadline is None:
        return
    completed_at = now()
    series.streak_current, series.streak_best = recurrence_rules.update_streak(
        series.streak_current, series.streak_best, recurrence_rules.is_on_time(task.deadline, completed_at)
    )
    open_sibling = await session.scalar(
        select(Task.id).where(
            Task.recurrence_id == series.id,
            Task.id != task.id,
            Task.deleted_at.is_(None),
            Task.status != TaskStatus.DONE,
        )
    )
    if open_sibling is not None:
        return
    shift = recurrence_rules.plan_next(
        recurrence_rules.parse_rule(series.rule), series.starts_on, task.deadline, completed_at
    )

    def moved(value: datetime | None) -> datetime | None:
        return value + shift.delta if value is not None else None

    following = Task(
        space_id=task.space_id,
        created_by_id=task.created_by_id,
        title=task.title,
        description=task.description,
        category=task.category,
        priority=task.priority,
        deadline=moved(task.deadline),
        remind_at=moved(task.remind_at),
        start_time=moved(task.start_time),
        end_time=moved(task.end_time),
        recurrence=series,
    )
    session.add(following)
    await _finish(session, following, push_google=push_google)


async def update_task(
    session: AsyncSession,
    task: Task,
    data: TaskUpdate,
    *,
    push_google: bool = True,
) -> Task:
    changes = data.model_dump(exclude_unset=True)
    was_done = task.status is TaskStatus.DONE
    rule_change = "recurrence" in changes
    rule = changes.pop("recurrence", None)
    if "status" in changes:
        changes["is_completed"] = changes["status"] is TaskStatus.DONE
    elif "is_completed" in changes:
        if changes["is_completed"]:
            changes["status"] = TaskStatus.DONE
        elif task.status is TaskStatus.DONE:
            changes["status"] = TaskStatus.TODO
    for field, value in changes.items():
        setattr(task, field, value)
    if task.start_time is not None and task.end_time is None:
        task.end_time = task.start_time + timedelta(hours=1)
    if rule_change:
        await _attach_recurrence(session, task, rule)
    elif task.recurrence is not None and task.recurrence.space_id != task.space_id:
        task.recurrence.space_id = task.space_id
    await _finish(session, task, push_google=push_google)
    if not was_done and task.status is TaskStatus.DONE:
        await _on_completed(session, task, push_google=push_google)
        await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task: Task, *, push_google: bool = True) -> None:
    """Soft delete: the row stays for history/export, the reminder and Google event go away."""
    task_id = task.id
    event_id = task.google_event_id
    task.deleted_at = datetime.now(UTC)
    task.google_event_id = None
    if task.recurrence is not None:
        # Deleting a recurring task stops the series.
        task.recurrence.deleted_at = task.deleted_at
    await session.commit()
    scheduler.cancel_reminder(task_id)
    if push_google and event_id:
        from app.services.google_calendar import delete_google_event

        try:
            await delete_google_event(event_id)
        except Exception:
            logger.exception("Google Calendar delete failed for event %s; local task is already gone", event_id)


async def _mirror_google(session: AsyncSession, task: Task) -> None:
    from app.services.google_calendar import (
        build_event_body,
        create_google_event,
        delete_google_event,
        is_configured,
        update_google_event,
    )

    if not is_configured():
        return

    has_event = build_event_body(task) is not None
    try:
        if task.google_event_id and not has_event:
            await delete_google_event(task.google_event_id)
            task.google_event_id = None
            await session.commit()
            return
        if not has_event:
            return
        if task.google_event_id:
            await update_google_event(task)
        else:
            task.google_event_id = await create_google_event(task)
        await session.commit()
    except Exception:
        logger.exception("Google Calendar mirror failed for task %s; the task stays saved", task.id)


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

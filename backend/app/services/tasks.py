import logging
from collections.abc import Sequence
from datetime import datetime, time, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scheduler
from app.config import TIMEZONE
from app.models import Task, User
from app.schemas import Assignee, TaskCreate, TaskScope, TaskUpdate
from app.services.reminders import next_fire_at, remind_at_for

logger = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now(TIMEZONE)


def _day_bounds(day_offset: int = 0) -> tuple[datetime, datetime]:
    start = datetime.combine(now().date() + timedelta(days=day_offset), time.min, tzinfo=TIMEZONE)
    return start, start + timedelta(days=1)


def sync_reminder(task: Task) -> None:
    run_at = next_fire_at(task, now())
    if run_at is None:
        scheduler.cancel_reminder(task.id)
    else:
        scheduler.schedule_reminder(task.id, run_at)


def apply_relative_reminder(task: Task, *, explicit_remind_at: bool, offset_changed: bool, anchor_changed: bool) -> None:
    """Keep remind_at at `remind_before_minutes` before the event.

    An explicit remind_at (snooze, "remind me at 10:00") wins for this write; the offset stays
    and re-applies the next time the event moves.
    """
    if task.remind_before_minutes is None or explicit_remind_at:
        return
    if offset_changed or anchor_changed:
        task.remind_at = remind_at_for(task.start_time, task.deadline, task.remind_before_minutes)


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


async def _partner_of(session: AsyncSession, user_id: int) -> int | None:
    user = await session.get(User, user_id)
    return user.partner_telegram_id if user else None


def _visible_to(user_id: int, partner: int | None):
    clauses = [
        Task.owner_id == user_id,
        Task.user_id == user_id,
        Task.assigned_to_id == user_id,
        Task.created_by_id == user_id,
    ]
    if partner is not None:
        clauses.append(and_(Task.is_shared.is_(True), Task.owner_id == partner))
    return or_(*clauses)


async def list_tasks(
    session: AsyncSession,
    user_id: int,
    scope: TaskScope = TaskScope.ALL,
    category: str | None = None,
) -> Sequence[Task]:
    partner = await _partner_of(session, user_id)
    stmt = select(Task).where(_visible_to(user_id, partner))

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
    if task is None:
        return None
    partner = await _partner_of(session, user_id)
    visible = user_id in (task.owner_id, task.user_id, task.assigned_to_id, task.created_by_id)
    if task.is_shared and partner is not None and task.owner_id == partner:
        visible = True
    return task if visible else None


async def create_task(
    session: AsyncSession,
    user_id: int,
    data: TaskCreate,
    *,
    push_google: bool = True,
) -> Task:
    raw = apply_schedule(data.model_dump())
    is_shared = bool(raw.pop("is_shared", False))
    for_partner = bool(raw.pop("for_partner", False)) and not is_shared
    assignee = raw.pop("assignee", None)
    if assignee is not None:
        is_shared = assignee == Assignee.SHARED
        for_partner = assignee == Assignee.PARTNER
    owner_id = user_id
    assigned_to_id = None
    if for_partner:
        partner = await _partner_of(session, user_id)
        if partner is not None:
            owner_id = partner
            assigned_to_id = partner
        else:
            logger.warning("for_partner ignored: user %s has no partner", user_id)
    task = Task(
        user_id=owner_id,
        owner_id=owner_id,
        is_shared=is_shared,
        assigned_to_id=assigned_to_id,
        created_by_id=user_id,
        **raw,
    )
    apply_relative_reminder(
        task,
        explicit_remind_at=raw.get("remind_at") is not None,
        offset_changed=True,
        anchor_changed=True,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    sync_reminder(task)
    if push_google:
        await _mirror_google(session, task)
    if task.owner_id != user_id or task.is_shared:
        await scheduler.notify_assigned(task, actor_id=user_id)
    return task


async def _apply_assignee(session: AsyncSession, task: Task, assignee: Assignee, actor_id: int | None) -> None:
    """Re-point a task at me, the partner, or both, as seen by whoever edits it."""
    actor = actor_id or task.owner_id or task.user_id
    if assignee == Assignee.SHARED:
        task.is_shared = True
        task.assigned_to_id = None
        if task.owner_id not in (actor, await _partner_of(session, actor)):
            task.owner_id = task.user_id = actor
        return
    task.is_shared = False
    if assignee == Assignee.ME:
        task.owner_id = task.user_id = actor
        task.assigned_to_id = None
        return
    partner = await _partner_of(session, actor)
    if partner is None:
        logger.warning("assignee=partner ignored: user %s has no partner", actor)
        return
    task.owner_id = task.user_id = task.assigned_to_id = partner


async def update_task(
    session: AsyncSession,
    task: Task,
    data: TaskUpdate,
    *,
    push_google: bool = True,
    actor_id: int | None = None,
) -> Task:
    was_completed = task.is_completed
    changes = data.model_dump(exclude_unset=True)
    assignee = changes.pop("assignee", None)
    anchor_before = (task.start_time, task.deadline)
    owner_before, shared_before = task.owner_id, task.is_shared
    old_events = await _google_copies(session, task) if push_google else []
    for field, value in changes.items():
        setattr(task, field, value)
    if assignee is not None:
        await _apply_assignee(session, task, Assignee(assignee), actor_id)
    handed_over = task.owner_id != owner_before or task.is_shared != shared_before
    if handed_over and push_google:
        # The events live in the old owner's (and partner's) calendars: remove them, the mirror below
        # writes fresh ones where the task now belongs.
        await _drop_google_copies(old_events)
        task.google_event_id = None
        task.partner_google_event_id = None
    if task.start_time is not None and task.end_time is None:
        task.end_time = task.start_time + timedelta(hours=1)
    apply_relative_reminder(
        task,
        explicit_remind_at="remind_at" in changes,
        offset_changed="remind_before_minutes" in changes,
        anchor_changed=(task.start_time, task.deadline) != anchor_before,
    )
    await session.commit()
    await session.refresh(task)
    sync_reminder(task)
    if push_google:
        await _mirror_google(session, task)
    if task.is_shared and not was_completed and task.is_completed:
        await scheduler.notify_shared_closed(task, actor_id=actor_id)
    elif not was_completed and task.is_completed:
        await scheduler.notify_done_for_author(task, actor_id=actor_id)
    if handed_over and actor_id is not None and task.owner_id != actor_id and not task.is_shared:
        await scheduler.notify_assigned(task, actor_id=actor_id)
    return task


async def _google_copies(session: AsyncSession, task: Task) -> list[tuple[str, str | None]]:
    """(event id, calendar) pairs this task currently has in Google."""
    from app.services.users import calendar_id_for

    copies: list[tuple[str, str | None]] = []
    owner = task.owner_id or task.user_id
    if task.google_event_id:
        copies.append((task.google_event_id, await calendar_id_for(session, owner)))
    if task.partner_google_event_id:
        partner = await _partner_of(session, owner)
        copies.append((task.partner_google_event_id, await calendar_id_for(session, partner) if partner else None))
    return copies


async def _drop_google_copies(copies: list[tuple[str, str | None]]) -> None:
    if not copies:
        return
    from app.services.google_calendar import delete_event, is_configured

    if not is_configured():
        return
    for event_id, calendar_id in copies:
        try:
            await delete_event(event_id, calendar_id=calendar_id)
        except Exception:
            logger.exception("Could not remove Google event %s after a hand-over", event_id)


async def delete_task(session: AsyncSession, task: Task, *, push_google: bool = True) -> None:
    task_id = task.id
    event_id = task.google_event_id
    partner_event_id = task.partner_google_event_id
    owner_id = task.owner_id
    await session.delete(task)
    await session.commit()
    scheduler.cancel_reminder(task_id)
    if not push_google:
        return
    from app.services.google_calendar import delete_event

    try:
        if event_id:
            await delete_event(event_id, calendar_id=await _calendar_for(owner_id))
        if partner_event_id:
            partner = await _partner_of_id(owner_id)
            await delete_event(partner_event_id, calendar_id=await _calendar_for(partner) if partner else None)
    except Exception:
        logger.exception("Google Calendar delete failed for task %s; local task is already gone", task_id)


async def _calendar_for(telegram_id: int | None) -> str | None:
    if telegram_id is None:
        return None
    from app.db import session_factory
    from app.services.users import calendar_id_for

    async with session_factory() as session:
        return await calendar_id_for(session, telegram_id)


async def _partner_of_id(telegram_id: int | None) -> int | None:
    if telegram_id is None:
        return None
    from app.db import session_factory

    async with session_factory() as session:
        return await _partner_of(session, telegram_id)


async def _mirror_google(session: AsyncSession, task: Task) -> None:
    from app.services.google_calendar import (
        GoogleEventMissing,
        build_event_body,
        create_event,
        delete_event,
        is_configured,
        update_event,
    )
    from app.services.users import calendar_id_for

    if not is_configured():
        return

    body = build_event_body(task)
    owner_calendar = await calendar_id_for(session, task.owner_id or task.user_id)
    partner = await _partner_of(session, task.owner_id or task.user_id)
    partner_calendar = await calendar_id_for(session, partner) if task.is_shared and partner else None
    try:
        task.google_event_id = await _sync_event(
            body,
            owner_calendar,
            task.google_event_id,
            create_event,
            update_event,
            delete_event,
            GoogleEventMissing,
        )
        if task.is_shared and partner_calendar and partner_calendar != owner_calendar:
            task.partner_google_event_id = await _sync_event(
                body,
                partner_calendar,
                task.partner_google_event_id,
                create_event,
                update_event,
                delete_event,
                GoogleEventMissing,
            )
        elif task.partner_google_event_id:
            await delete_event(task.partner_google_event_id, calendar_id=partner_calendar)
            task.partner_google_event_id = None
        await session.commit()
    except Exception:
        logger.exception("Google Calendar mirror failed for task %s; the task stays saved", task.id)


async def _sync_event(body, calendar_id, event_id, create_event, update_event, delete_event, missing):
    from app.services.google_calendar import _spec_from_body

    if not calendar_id:
        return event_id
    spec = _spec_from_body(body) if body is not None else None
    if spec is None:
        if event_id:
            await delete_event(event_id, calendar_id=calendar_id)
        return None
    if event_id:
        try:
            await update_event(event_id, calendar_id=calendar_id, **spec)
            return event_id
        except missing:
            pass
    return await create_event(calendar_id=calendar_id, **spec)


async def complete_task(session: AsyncSession, task: Task, *, actor_id: int | None = None) -> Task:
    return await update_task(session, task, TaskUpdate(is_completed=True), actor_id=actor_id)


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

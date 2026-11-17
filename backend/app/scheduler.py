import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.bot.keyboards import reminder_keyboard
from app.bot.texts import reminder_text
from app.config import TIMEZONE, Settings
from app.db import session_factory
from app.models import Task

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(
    timezone=TIMEZONE,
    job_defaults={"coalesce": True, "misfire_grace_time": 60 * 60},
)

_bot: Bot | None = None


def setup_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    global _bot
    _bot = bot
    scheduler.configure(
        jobstores={
            "default": SQLAlchemyJobStore(
                url=settings.scheduler_database_url,
                tablename="apscheduler_jobs",
            )
        }
    )
    _configure_google_job(settings)
    _configure_external_feeds()
    return scheduler


def _configure_google_job(settings: Settings) -> None:
    job_id = "google-calendar-sync"
    enabled = bool(settings.google_service_account_file or (settings.google_client_id and settings.google_client_secret))
    if not enabled:
        return
    scheduler.add_job(
        "app.services.google_calendar:refresh_google_watch",
        trigger=IntervalTrigger(hours=6, timezone=TIMEZONE),
        id=job_id,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def _configure_external_feeds() -> None:
    scheduler.add_job(
        "app.services.external_calendars:refresh_external_feeds",
        trigger=IntervalTrigger(minutes=30, timezone=TIMEZONE),
        id="external-calendars-sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def _job_id(task_id: int) -> str:
    return f"task-reminder:{task_id}"


def schedule_reminder(
    task_id: int,
    run_at: datetime,
    *,
    previous: dict[int, int] | None = None,
    nag_count: int = 0,
) -> None:
    """One job per task. `previous` (chat → message) and `nag_count` carry a nag chain along."""
    scheduler.add_job(
        send_reminder,
        trigger=DateTrigger(run_date=run_at, timezone=TIMEZONE),
        id=_job_id(task_id),
        args=[task_id],
        kwargs={"previous": previous or {}, "nag_count": nag_count},
        replace_existing=True,
    )
    logger.info("Reminder for task %s scheduled at %s", task_id, run_at.astimezone(TIMEZONE))


def cancel_reminder(task_id: int) -> None:
    try:
        scheduler.remove_job(_job_id(task_id))
    except JobLookupError:
        pass


async def send_reminder(task_id: int, previous: dict | None = None, nag_count: int = 0) -> None:
    """APScheduler job; referenced by import path, so keep it module-level.

    For high-priority tasks it re-schedules itself ("додовбувач") and removes the previous
    nag message, so the chat shows one live reminder instead of a wall of them.
    """
    if _bot is None:
        logger.error("Scheduler fired before the bot was configured")
        return

    from app.services.reminders import next_nag_at

    async with session_factory() as session:
        task = await session.get(Task, task_id)
        await _delete_messages(previous or {})
        if task is None or task.is_completed:
            return
        recipients = {task.user_id, task.owner_id}
        if task.assigned_to_id:
            recipients.add(task.assigned_to_id)
        if task.is_shared:
            from app.services.users import partner_id

            other = await partner_id(session, task.owner_id or task.user_id)
            if other:
                recipients.add(other)

        follow_up = next_nag_at(task, datetime.now(TIMEZONE))
        sent: dict[int, int] = {}
        for chat_id in recipients:
            if not chat_id:
                continue
            message = await _bot.send_message(
                chat_id=chat_id,
                text=reminder_text(task, nag_count=nag_count, nagging=follow_up is not None),
                reply_markup=reminder_keyboard(task.id),
            )
            sent[chat_id] = message.message_id

    if follow_up is not None:
        schedule_reminder(task_id, follow_up, previous=sent, nag_count=nag_count + 1)


async def _delete_messages(messages: dict) -> None:
    for chat_id, message_id in messages.items():
        try:
            await _bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
        except Exception:
            # Already deleted by hand, too old, or edited into a status line: keep going.
            logger.debug("Could not delete nag message %s in %s", message_id, chat_id)


async def notify_shared_closed(task: Task, actor_id: int | None) -> None:
    if _bot is None or not task.is_shared:
        return
    from app.services.users import partner_id

    async with session_factory() as session:
        owner = task.owner_id or task.user_id
        partner = await partner_id(session, owner)
    other = partner if actor_id in (None, owner) else owner
    if other is None or other == actor_id:
        return
    await _bot.send_message(chat_id=other, text=f"⚡️ Спільну задачу «{task.title}» закрито.")


def schedule_digests(users: list) -> None:
    slots = (
        ("morning", "morning_time", "Ранок"),
        ("afternoon", "afternoon_time", "День"),
        ("evening", "evening_time", "Вечір"),
    )
    for user in users:
        for slot, attr, _label in slots:
            clock = getattr(user, attr)
            scheduler.add_job(
                send_digest,
                trigger=CronTrigger(hour=clock.hour, minute=clock.minute, timezone=TIMEZONE),
                id=f"digest:{user.telegram_id}:{slot}",
                args=[user.telegram_id, slot],
                replace_existing=True,
            )


async def send_digest(telegram_id: int, slot: str) -> None:
    if _bot is None:
        return
    from app.services.tasks import list_tasks
    from app.schemas import TaskScope

    labels = {"morning": "Ранок", "afternoon": "День", "evening": "Вечір"}
    async with session_factory() as session:
        tasks = await list_tasks(session, telegram_id, TaskScope.TODAY)
    open_tasks = [task for task in tasks if not task.is_completed]
    if not open_tasks:
        return
    lines = "\n".join(f"• {task.title}" for task in open_tasks[:12])
    await _bot.send_message(chat_id=telegram_id, text=f"{labels.get(slot, 'Нагадування')}\n{lines}")

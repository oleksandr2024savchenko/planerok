import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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
    return scheduler


def _configure_google_job(settings: Settings) -> None:
    job_id = "google-calendar-sync"
    enabled = bool(settings.google_service_account_file or (settings.google_client_id and settings.google_client_secret))
    if not enabled:
        try:
            scheduler.remove_job(job_id)
        except JobLookupError:
            pass
        return
    scheduler.add_job(
        "app.services.google_calendar:refresh_google_watch",
        trigger=IntervalTrigger(hours=6, timezone=TIMEZONE),
        id=job_id,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def _job_id(task_id: int) -> str:
    return f"task-reminder:{task_id}"


def schedule_reminder(task_id: int, run_at: datetime) -> None:
    trigger = DateTrigger(run_date=run_at, timezone=TIMEZONE)
    job_id = _job_id(task_id)
    if scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger=trigger)
    else:
        scheduler.add_job(
            send_reminder,
            trigger=trigger,
            id=job_id,
            args=[task_id],
            replace_existing=True,
        )
    logger.info("Reminder for task %s scheduled at %s", task_id, run_at.astimezone(TIMEZONE))


def cancel_reminder(task_id: int) -> None:
    try:
        scheduler.remove_job(_job_id(task_id))
    except JobLookupError:
        pass


async def send_reminder(task_id: int) -> None:
    """APScheduler job; referenced by import path, so keep it module-level."""
    if _bot is None:
        logger.error("Scheduler fired before the bot was configured")
        return

    async with session_factory() as session:
        task = await session.get(Task, task_id)
        if task is None or task.is_completed:
            return
        await _bot.send_message(
            chat_id=task.user_id,
            text=reminder_text(task),
            reply_markup=reminder_keyboard(task.id),
        )

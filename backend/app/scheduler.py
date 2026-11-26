import logging
from datetime import datetime
from html import escape

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


def _timer_job_id(timer_id: int) -> str:
    return f"task-timer:{timer_id}"


def schedule_timer(timer_id: int, run_at_ts: float) -> None:
    scheduler.add_job(
        finish_timer,
        trigger=DateTrigger(run_date=datetime.fromtimestamp(run_at_ts, TIMEZONE), timezone=TIMEZONE),
        id=_timer_job_id(timer_id),
        args=[timer_id],
        replace_existing=True,
        misfire_grace_time=6 * 60 * 60,
    )


def cancel_timer(timer_id: int) -> None:
    try:
        scheduler.remove_job(_timer_job_id(timer_id))
    except JobLookupError:
        pass


async def finish_timer(timer_id: int) -> None:
    """APScheduler job: the session is over. Credit the time and offer a break or another round."""
    from app.bot.keyboards import break_done_keyboard, focus_done_keyboard
    from app.bot.texts import format_minutes
    from app.services import timers

    async with session_factory() as session:
        timer = await timers.finish(session, timer_id)
        if timer is None:
            return
        task = await session.get(Task, timer.task_id)
    if _bot is None or task is None:
        return
    minutes = max(timer.duration_seconds // 60, 1)
    if timer.kind == timers.FOCUS:
        text = (
            f"✅ <b>{minutes} хв фокусу</b> на «{escape(task.title)}» позаду.\n"
            f"Разом на задачу: {format_minutes(task.focused_seconds)}. Час на перерву?"
        )
        markup = focus_done_keyboard(task.id, minutes)
    else:
        text = f"☕ Перерва скінчилась. Повертаємось до «{escape(task.title)}»?"
        markup = break_done_keyboard(task.id)
    try:
        await _bot.send_message(chat_id=timer.user_id, text=text, reply_markup=markup)
    except Exception:
        logger.exception("Could not send the timer note for %s", timer_id)


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


async def _first_name(session, telegram_id: int | None) -> str:
    from app.models import User

    user = await session.get(User, telegram_id) if telegram_id else None
    return (user.first_name if user and user.first_name else None) or "Партнер"


async def notify_assigned(task: Task, actor_id: int | None) -> None:
    """Tell the other person that a task was written for them (or for both of you)."""
    if _bot is None or actor_id is None:
        return
    from app.bot.texts import task_details
    from app.services.users import partner_id

    async with session_factory() as session:
        other = await partner_id(session, actor_id)
        author = await _first_name(session, actor_id)
    if other is None or other == actor_id:
        return
    if not task.is_shared and other not in (task.owner_id, task.assigned_to_id):
        return
    header = f"⚡️ <b>{escape(author)}</b> додає спільну задачу" if task.is_shared else f"📌 Задача для тебе від <b>{escape(author)}</b>"
    from app.bot.keyboards import webapp_keyboard
    from app.config import get_settings

    try:
        await _bot.send_message(
            chat_id=other,
            text=f"{header}\n\n{task_details(task)}",
            reply_markup=webapp_keyboard(get_settings().webapp_url),
        )
    except Exception:
        logger.exception("Could not tell %s about task %s", other, task.id)


async def notify_import(actor_id: int, count: int, title: str | None, *, shared: bool) -> None:
    """One summary for the partner instead of a message per imported lesson."""
    if _bot is None or count <= 0:
        return
    from app.bot.keyboards import webapp_keyboard
    from app.config import get_settings
    from app.services.users import partner_id

    async with session_factory() as session:
        other = await partner_id(session, actor_id)
        who = await _first_name(session, actor_id)
    if other is None:
        return
    source = f" з розкладу «{escape(title)}»" if title else " з розкладу"
    noun = "подію" if count % 10 == 1 and count % 100 != 11 else "події" if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14) else "подій"
    what = f"{count} {'спільну' if noun == 'подію' else 'спільні' if noun == 'події' else 'спільних'} {noun}" if shared else f"{count} {noun} для тебе"
    try:
        await _bot.send_message(
            chat_id=other,
            text=f"📅 <b>{escape(who)}</b> додає {what}{source}.",
            reply_markup=webapp_keyboard(get_settings().webapp_url),
        )
    except Exception:
        logger.exception("Could not tell %s about an imported timetable", other)


async def notify_cancelled(title: str, recipients: set[int], actor_id: int) -> None:
    """A task that concerned the partner was cancelled: say so, so nobody waits for it."""
    if _bot is None or not recipients:
        return
    async with session_factory() as session:
        who = await _first_name(session, actor_id)
    for chat_id in recipients:
        try:
            await _bot.send_message(chat_id=chat_id, text=f"❌ <b>{escape(who)}</b> скасовує «{escape(title)}»")
        except Exception:
            logger.exception("Could not tell %s about a cancelled task", chat_id)


async def notify_done_for_author(task: Task, actor_id: int | None) -> None:
    """A task given to the partner was done: let its author know."""
    author = task.created_by_id
    if _bot is None or author is None or actor_id is None or author == actor_id:
        return
    async with session_factory() as session:
        doer = await _first_name(session, actor_id)
    try:
        await _bot.send_message(chat_id=author, text=f"✅ <b>{escape(doer)}</b>: «{escape(task.title)}» — виконано")
    except Exception:
        logger.exception("Could not tell %s that task %s is done", author, task.id)


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

from datetime import timedelta

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import ReminderAction, ReminderCallback
from app.bot.texts import format_dt, task_details
from app.services import tasks as tasks_service

router = Router(name="reminders")


@router.callback_query(ReminderCallback.filter())
async def on_reminder_action(
    callback: CallbackQuery,
    callback_data: ReminderCallback,
    session: AsyncSession,
) -> None:
    task = await tasks_service.get_task(session, callback.from_user.id, callback_data.task_id)
    if task is None:
        await callback.answer("Задачу не знайдено — можливо, її вже видалено.", show_alert=True)
        return

    match callback_data.action:
        case ReminderAction.DONE:
            task = await tasks_service.complete_task(session, task)
            status, toast = "✅ <b>Виконано</b>", "Чудова робота! 🎉"
        case ReminderAction.SNOOZE_15M:
            task = await tasks_service.snooze_task(session, task, timedelta(minutes=15))
            status, toast = f"⏳ Нагадаю {format_dt(task.remind_at)}", "Відкладено на 15 хв"
        case ReminderAction.SNOOZE_1H:
            task = await tasks_service.snooze_task(session, task, timedelta(hours=1))
            status, toast = f"⏳ Нагадаю {format_dt(task.remind_at)}", "Відкладено на 1 год"
        case ReminderAction.TOMORROW:
            task = await tasks_service.postpone_to_tomorrow(session, task)
            status, toast = f"📅 Перенесено: нагадаю {format_dt(task.remind_at)}", "Перенесено на завтра"

    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"{status}\n\n{task_details(task)}", reply_markup=None)
    await callback.answer(toast)

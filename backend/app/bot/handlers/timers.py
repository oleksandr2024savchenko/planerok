from html import escape

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import TimerAction, TimerCallback
from app.services import tasks as tasks_service
from app.services import timers

router = Router(name="timers")


@router.callback_query(TimerCallback.filter())
async def on_timer_action(callback: CallbackQuery, callback_data: TimerCallback, session: AsyncSession) -> None:
    task = await tasks_service.get_task(session, callback.from_user.id, callback_data.task_id)
    message = callback.message if isinstance(callback.message, Message) else None
    if task is None:
        await callback.answer("Задачу не знайдено — можливо, її вже видалено.", show_alert=True)
        return

    title = escape(task.title)
    match callback_data.action:
        case TimerAction.BREAK:
            await timers.start(session, callback.from_user.id, task, callback_data.minutes, kind=timers.BREAK)
            status, toast = f"☕ Перерва {callback_data.minutes} хв. Напишу, коли час повертатись до «{title}».", "Відпочивай"
        case TimerAction.FOCUS:
            await timers.start(session, callback.from_user.id, task, callback_data.minutes)
            status, toast = f"⏱ Фокус {callback_data.minutes} хв на «{title}» пішов.", "Поїхали!"
        case TimerAction.DONE:
            await tasks_service.complete_task(session, task, actor_id=callback.from_user.id)
            status, toast = f"✅ «{title}» — виконано", "Чудова робота! 🎉"
        case _:
            status, toast = None, "Добре"

    if message is not None:
        if status:
            await message.edit_text(status, reply_markup=None)
        else:
            await message.edit_reply_markup(reply_markup=None)
    await callback.answer(toast)

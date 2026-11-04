from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import ReminderAction, ReminderCallback, TaskAction, TaskActionCallback


def webapp_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗓 Відкрити планер", web_app=WebAppInfo(url=webapp_url))
    return builder.as_markup()


def created_tasks_keyboard(task_ids: list[int], webapp_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if len(task_ids) == 1:
        task_id = task_ids[0]
        builder.button(
            text="✏️ Змінити час",
            callback_data=TaskActionCallback(action=TaskAction.EDIT_TIME, task_id=task_id),
        )
        builder.button(
            text="🗑 Видалити",
            callback_data=TaskActionCallback(action=TaskAction.DELETE, task_id=task_id),
        )
        builder.button(text="📱 Відкрити в Mini App", web_app=WebAppInfo(url=webapp_url))
        builder.adjust(2, 1)
        return builder.as_markup()

    for index, task_id in enumerate(task_ids, start=1):
        builder.button(
            text=f"✏️ {index}",
            callback_data=TaskActionCallback(action=TaskAction.EDIT_TIME, task_id=task_id),
        )
        builder.button(
            text=f"🗑 {index}",
            callback_data=TaskActionCallback(action=TaskAction.DELETE, task_id=task_id),
        )
    builder.button(text="📱 Відкрити в Mini App", web_app=WebAppInfo(url=webapp_url))
    builder.adjust(*([2] * len(task_ids)), 1)
    return builder.as_markup()


def reminder_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("✅ Виконано", ReminderAction.DONE),
        ("⏳ +15 хв", ReminderAction.SNOOZE_15M),
        ("⏳ +1 год", ReminderAction.SNOOZE_1H),
        ("📅 На завтра", ReminderAction.TOMORROW),
    ]
    for text, action in buttons:
        builder.button(text=text, callback_data=ReminderCallback(action=action, task_id=task_id))
    builder.adjust(1, 3)
    return builder.as_markup()

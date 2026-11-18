from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import (
    ReminderAction,
    ReminderCallback,
    ReminderOffsetCallback,
    TaskAction,
    TaskActionCallback,
)
from app.services.reminders import PRESET_OFFSETS, format_offset

CLEAR_OFFSET = -1
CUSTOM_OFFSET = -2
BACK_FROM_OFFSET = -3


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
            text="🔔 Нагадати за…",
            callback_data=TaskActionCallback(action=TaskAction.REMIND, task_id=task_id),
        )
        builder.button(
            text="🗑 Видалити",
            callback_data=TaskActionCallback(action=TaskAction.DELETE, task_id=task_id),
        )
        builder.button(text="📱 Відкрити в Mini App", web_app=WebAppInfo(url=webapp_url))
        builder.adjust(2, 1, 1)
        return builder.as_markup()

    for index, task_id in enumerate(task_ids, start=1):
        builder.button(
            text=f"✏️ {index}",
            callback_data=TaskActionCallback(action=TaskAction.EDIT_TIME, task_id=task_id),
        )
        builder.button(
            text=f"🔔 {index}",
            callback_data=TaskActionCallback(action=TaskAction.REMIND, task_id=task_id),
        )
        builder.button(
            text=f"🗑 {index}",
            callback_data=TaskActionCallback(action=TaskAction.DELETE, task_id=task_id),
        )
    builder.button(text="📱 Відкрити в Mini App", web_app=WebAppInfo(url=webapp_url))
    builder.adjust(*([3] * len(task_ids)), 1)
    return builder.as_markup()


def reminder_offset_keyboard(task_id: int, current: int | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for minutes in PRESET_OFFSETS:
        label = format_offset(minutes)
        label = label[0].upper() + label[1:]
        builder.button(
            text=f"✓ {label}" if minutes == current else label,
            callback_data=ReminderOffsetCallback(task_id=task_id, minutes=minutes),
        )
    builder.button(
        text="✏️ Свій інтервал",
        callback_data=ReminderOffsetCallback(task_id=task_id, minutes=CUSTOM_OFFSET),
    )
    builder.button(
        text="🔕 Без нагадування",
        callback_data=ReminderOffsetCallback(task_id=task_id, minutes=CLEAR_OFFSET),
    )
    builder.button(
        text="← Назад",
        callback_data=ReminderOffsetCallback(task_id=task_id, minutes=BACK_FROM_OFFSET),
    )
    builder.adjust(1, 2, 2, 2, 2, 1)
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
    builder.button(text="❌ Скасувати", callback_data=ReminderCallback(action=ReminderAction.CANCEL, task_id=task_id))
    builder.adjust(1, 3, 1)
    return builder.as_markup()


def confirm_cancel_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="❌ Так, скасувати",
        callback_data=ReminderCallback(action=ReminderAction.CANCEL_YES, task_id=task_id),
    )
    builder.button(text="← Ні", callback_data=ReminderCallback(action=ReminderAction.KEEP, task_id=task_id))
    builder.adjust(2)
    return builder.as_markup()

from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class ReminderAction(StrEnum):
    DONE = "done"
    SNOOZE_15M = "s15"
    SNOOZE_1H = "s60"
    TOMORROW = "tmr"


class ReminderCallback(CallbackData, prefix="rem"):
    action: ReminderAction
    task_id: int


class TaskAction(StrEnum):
    EDIT_TIME = "time"
    DELETE = "del"


class TaskActionCallback(CallbackData, prefix="task"):
    action: TaskAction
    task_id: int

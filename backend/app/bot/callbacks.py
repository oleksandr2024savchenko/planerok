from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class ReminderAction(StrEnum):
    DONE = "done"
    SNOOZE_15M = "s15"
    SNOOZE_1H = "s60"
    TOMORROW = "tmr"
    CANCEL = "cnl"  # asks «точно?»
    CANCEL_YES = "cny"  # deletes the task
    KEEP = "keep"  # back to the reminder buttons


class ReminderCallback(CallbackData, prefix="rem"):
    action: ReminderAction
    task_id: int


class TaskAction(StrEnum):
    EDIT_TIME = "time"
    DELETE = "del"
    REMIND = "rem"


class ReminderOffsetCallback(CallbackData, prefix="off"):
    """minutes = -1 clears the reminder, -2 asks for a custom interval, -3 goes back."""

    task_id: int
    minutes: int


class TaskActionCallback(CallbackData, prefix="task"):
    action: TaskAction
    task_id: int

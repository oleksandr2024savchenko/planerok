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


class TimerAction(StrEnum):
    BREAK = "brk"  # start a break of `minutes`
    FOCUS = "go"  # start another focus session of `minutes`
    DONE = "done"  # mark the task done
    LATER = "later"  # just hide the buttons


class TimerCallback(CallbackData, prefix="tmr"):
    action: TimerAction
    task_id: int
    minutes: int = 0


class ImportCallback(CallbackData, prefix="imp"):
    """Who gets a timetable read from a PDF: me / partner / shared, or cancel."""

    choice: str


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

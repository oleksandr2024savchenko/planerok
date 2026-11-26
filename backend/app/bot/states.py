from aiogram.fsm.state import State, StatesGroup


class TaskEdit(StatesGroup):
    waiting_for_time = State()
    waiting_for_offset = State()


class ScheduleImportState(StatesGroup):
    choosing_assignee = State()

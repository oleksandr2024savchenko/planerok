from aiogram.fsm.state import State, StatesGroup


class TaskEdit(StatesGroup):
    waiting_for_time = State()

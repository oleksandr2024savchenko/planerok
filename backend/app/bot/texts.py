from datetime import datetime, timedelta
from html import escape

from app.config import TIMEZONE
from app.models import Priority, Task

PRIORITY_LABELS: dict[Priority, str] = {
    Priority.LOW: "▫️ Низький",
    Priority.MEDIUM: "🔸 Середній",
    Priority.HIGH: "🔺 Високий",
}


def format_dt(value: datetime) -> str:
    local = value.astimezone(TIMEZONE)
    today = datetime.now(TIMEZONE).date()
    if local.date() == today:
        day = "сьогодні"
    elif local.date() == today + timedelta(days=1):
        day = "завтра"
    else:
        day = local.strftime("%d.%m.%Y")
    return f"{day} о {local:%H:%M}"


def task_details(task: Task) -> str:
    lines = [f"<b>{escape(task.title)}</b>"]
    if task.description:
        lines.append(f"<i>{escape(task.description)}</i>")
    meta: list[str] = []
    if task.category:
        meta.append(f"#{escape(task.category)}")
    meta.append(PRIORITY_LABELS[task.priority])
    lines.append(" · ".join(meta))
    if task.deadline:
        lines.append(f"📅 Дедлайн: {format_dt(task.deadline)}")
    if task.remind_at and not task.is_completed:
        lines.append(f"🔔 Нагадування: {format_dt(task.remind_at)}")
    return "\n".join(lines)


def reminder_text(task: Task) -> str:
    return f"⏰ <b>Нагадування</b>\n\n{task_details(task)}"


def created_text(task: Task) -> str:
    return f"✨ Задачу додано\n\n{task_details(task)}"


def created_list_text(tasks: list[Task]) -> str:
    if len(tasks) == 1:
        return created_text(tasks[0])
    blocks = [f"✨ Створив <b>{len(tasks)}</b> задачі:"]
    for index, task in enumerate(tasks, start=1):
        blocks.append(f"{index}. {task_details(task)}")
    return "\n\n".join(blocks)


ASK_NEW_TIME_TEXT = (
    "✏️ Надішли новий час нагадування.\n"
    "Наприклад: <code>завтра о 10:00</code> або <code>через 2 години</code>."
)


START_TEXT = (
    "👋 Привіт! Я твій персональний планер.\n\n"
    "Напиши задачу звичайною мовою або надішли <b>голосове</b> — я сам розпізнаю "
    "назву, категорію, дедлайн і нагадування.\n\n"
    "Наприклад:\n"
    "• <code>завтра на 10 ранку зал</code>\n"
    "• <code>Здати звіт у п'ятницю о 18:00, після цього купити продукти</code>\n\n"
    "А для повного огляду відкрий планер 👇"
)

HELP_TEXT = START_TEXT

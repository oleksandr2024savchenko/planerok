from datetime import datetime, timedelta
from html import escape

from app.config import TIMEZONE
from app.models import Priority, Task

PRIORITY_LABELS: dict[Priority, str] = {
    Priority.LOW: "▫️ Низький",
    Priority.MEDIUM: "🔸 Середній",
    Priority.HIGH: "🔺 Високий",
}


def format_day(value: datetime) -> str:
    local = value.astimezone(TIMEZONE)
    today = datetime.now(TIMEZONE).date()
    if local.date() == today:
        return "сьогодні"
    if local.date() == today + timedelta(days=1):
        return "завтра"
    return local.strftime("%d.%m.%Y")


def format_dt(value: datetime) -> str:
    local = value.astimezone(TIMEZONE)
    return f"{format_day(local)} о {local:%H:%M}"


def _same_minute(left: datetime, right: datetime) -> bool:
    a = left.astimezone(TIMEZONE).replace(second=0, microsecond=0)
    b = right.astimezone(TIMEZONE).replace(second=0, microsecond=0)
    return a == b


def schedule_line(task: Task) -> str | None:
    start = task.start_time.astimezone(TIMEZONE) if task.start_time else None
    end = task.end_time.astimezone(TIMEZONE) if task.end_time else None
    if start is not None and end is not None:
        if start.date() == end.date():
            return f"📅 {format_dt(start)}–{end:%H:%M}"
        return f"📅 {format_dt(start)} – {format_dt(end)}"
    if start is not None:
        return f"📅 {format_dt(start)}"
    if task.deadline is None:
        return None
    local = task.deadline.astimezone(TIMEZONE)
    if local.hour == 23 and local.minute == 59:
        return f"📅 {format_day(local)}"
    return f"📅 Дедлайн: {format_dt(task.deadline)}"


def task_details(task: Task) -> str:
    lines = [f"<b>{escape(task.title)}</b>"]
    if task.description:
        lines.append(f"<i>{escape(task.description)}</i>")
    meta: list[str] = []
    if task.category:
        meta.append(f"#{escape(task.category)}")
    meta.append(PRIORITY_LABELS[task.priority])
    lines.append(" · ".join(meta))
    if line := schedule_line(task):
        lines.append(line)
    anchor = task.start_time or task.deadline
    if task.remind_at and not task.is_completed and (anchor is None or not _same_minute(task.remind_at, anchor)):
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

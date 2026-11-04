from datetime import datetime

from app.bot.texts import task_details
from app.config import TIMEZONE
from app.models import Priority, Task


def _task(**overrides: object) -> Task:
    data: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "title": "Зустріч",
        "priority": Priority.MEDIUM,
        "is_completed": False,
    }
    data.update(overrides)
    return Task(**data)


def test_schedule_line_shows_a_same_day_range() -> None:
    text = task_details(
        _task(
            start_time=datetime(2027, 3, 15, 10, 0, tzinfo=TIMEZONE),
            end_time=datetime(2027, 3, 15, 11, 30, tzinfo=TIMEZONE),
            remind_at=datetime(2027, 3, 15, 9, 45, tzinfo=TIMEZONE),
        )
    )
    assert "15.03.2027 о 10:00–11:30" in text
    assert "Нагадування" in text
    assert "09:45" in text


def test_schedule_line_hides_a_reminder_that_matches_the_start() -> None:
    when = datetime(2027, 3, 15, 10, 0, tzinfo=TIMEZONE)
    text = task_details(_task(deadline=when, remind_at=when))
    assert text.count("10:00") == 1
    assert "Нагадування" not in text


def test_date_only_deadline_omits_the_end_of_day_clock() -> None:
    text = task_details(_task(deadline=datetime(2027, 3, 15, 23, 59, tzinfo=TIMEZONE)))
    assert "15.03.2027" in text
    assert "23:59" not in text

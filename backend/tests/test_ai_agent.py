from datetime import datetime, timedelta

from app.config import TIMEZONE
from app.models import Priority
from app.services.ai_agent import (
    ParsedTask,
    WEEKDAYS_UK,
    build_system_prompt,
    finalize_task,
    to_task_create,
)

NOW = datetime(2026, 11, 3, 16, 0, tzinfo=TIMEZONE)


def test_system_prompt_includes_vienna_clock_and_weekday() -> None:
    prompt = build_system_prompt(NOW)
    assert "Europe/Vienna" in prompt
    assert WEEKDAYS_UK[NOW.weekday()] in prompt
    assert "2026-11-03T16:00" in prompt
    assert "вівторок" in prompt


def test_finalize_sets_reminder_15_minutes_before_event_time() -> None:
    deadline = datetime(2026, 11, 4, 10, 0, tzinfo=TIMEZONE)
    task = finalize_task(
        ParsedTask(title="Зал", category="training", priority="medium", deadline=deadline),
        now=NOW,
    )
    assert task.remind_at == deadline - timedelta(minutes=15)


def test_finalize_keeps_explicit_reminder() -> None:
    deadline = datetime(2026, 11, 4, 10, 0, tzinfo=TIMEZONE)
    remind_at = datetime(2026, 11, 4, 9, 0, tzinfo=TIMEZONE)
    task = finalize_task(
        ParsedTask(
            title="Зал",
            category="training",
            deadline=deadline,
            remind_at=remind_at,
        ),
        now=NOW,
    )
    assert task.remind_at == remind_at


def test_finalize_skips_default_reminder_for_date_only_deadline() -> None:
    deadline = datetime(2026, 11, 4, 23, 59, tzinfo=TIMEZONE)
    task = finalize_task(
        ParsedTask(title="Оплатити рахунок", category="personal", deadline=deadline),
        now=NOW,
    )
    assert task.remind_at is None


def test_naive_datetimes_are_localized_to_vienna() -> None:
    task = ParsedTask.model_validate(
        {
            "title": "Звіт",
            "category": "work",
            "priority": "high",
            "deadline": "2026-11-07T18:00:00",
        }
    )
    assert task.deadline is not None
    assert task.deadline.tzinfo is not None
    assert task.deadline.astimezone(TIMEZONE).hour == 18


def test_to_task_create_maps_category_to_ukrainian_slug() -> None:
    created = to_task_create(
        ParsedTask(title="Пробіжка", category="training", priority="low"),
    )
    assert created.category == "тренування"
    assert created.priority is Priority.LOW

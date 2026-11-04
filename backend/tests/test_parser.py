from datetime import datetime

import pytest

from app.bot.parser import EmptyTitleError, parse_task
from app.config import TIMEZONE
from app.models import Priority

NOW = datetime(2026, 11, 3, 16, 0, tzinfo=TIMEZONE)


def test_plain_text_becomes_title() -> None:
    parsed = parse_task("Купити молоко", now=NOW)
    assert parsed.title == "Купити молоко"
    assert parsed.priority is Priority.MEDIUM
    assert parsed.deadline is None
    assert parsed.remind_at is None


def test_full_syntax() -> None:
    parsed = parse_task("Здати звіт завтра о 10:00 #Робота !!!", now=NOW)
    assert parsed.title == "Здати звіт"
    assert parsed.category == "робота"
    assert parsed.priority is Priority.HIGH
    assert parsed.deadline == datetime(2026, 11, 4, 10, 0, tzinfo=TIMEZONE)
    assert parsed.remind_at == parsed.deadline


def test_past_time_without_date_rolls_to_tomorrow() -> None:
    parsed = parse_task("Подзвонити мамі 09:30", now=NOW)
    assert parsed.remind_at == datetime(2026, 11, 4, 9, 30, tzinfo=TIMEZONE)


def test_explicit_date_without_time_sets_end_of_day_deadline() -> None:
    parsed = parse_task("Оплатити рахунок 25.12 !", now=NOW)
    assert parsed.title == "Оплатити рахунок"
    assert parsed.priority is Priority.LOW
    assert parsed.deadline == datetime(2026, 12, 25, 23, 59, tzinfo=TIMEZONE)
    assert parsed.remind_at is None


def test_past_date_rolls_to_next_year() -> None:
    parsed = parse_task("Річниця 01.02", now=NOW)
    assert parsed.deadline is not None and parsed.deadline.year == 2027


def test_extra_lines_become_description() -> None:
    parsed = parse_task("Тренування післязавтра о 19:00 #тренування\nНоги + кардіо", now=NOW)
    assert parsed.title == "Тренування"
    assert parsed.description == "Ноги + кардіо"
    assert parsed.deadline == datetime(2026, 11, 5, 19, 0, tzinfo=TIMEZONE)


def test_exclamation_inside_word_is_not_priority() -> None:
    parsed = parse_task("Привіт!", now=NOW)
    assert parsed.title == "Привіт!"
    assert parsed.priority is Priority.MEDIUM


def test_empty_title_raises() -> None:
    with pytest.raises(EmptyTitleError):
        parse_task("#робота завтра", now=NOW)

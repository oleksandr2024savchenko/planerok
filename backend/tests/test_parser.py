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


def test_at_date_tokens() -> None:
    assert parse_task("Звіт @завтра", now=NOW).deadline == datetime(2026, 11, 4, 23, 59, tzinfo=TIMEZONE)
    parsed = parse_task("Подарунок @25.12", now=NOW)
    assert parsed.title == "Подарунок"
    assert parsed.deadline == datetime(2026, 12, 25, 23, 59, tzinfo=TIMEZONE)


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("Звіт @пт", 6),  # NOW is Tuesday 3.11 → Friday 6.11
        ("Звіт у п'ятницю о 18:00", 6),
        ("Зал @вт", 3),  # same weekday → today
        ("Зал @нд", 8),
    ],
)
def test_weekdays(text: str, day: int) -> None:
    parsed = parse_task(text, now=NOW)
    assert parsed.title in {"Звіт", "Зал"}
    assert parsed.deadline is not None
    assert parsed.deadline.date() == datetime(2026, 11, day).date()


def test_plan_example_with_space_tag_and_priority() -> None:
    parsed = parse_task("Звіт #Бізнес !high @завтра", now=NOW)
    assert parsed.title == "Звіт"
    assert parsed.category == "бізнес"
    assert parsed.priority is Priority.HIGH
    assert parsed.deadline == datetime(2026, 11, 4, 23, 59, tzinfo=TIMEZONE)


def test_short_weekday_needs_at_sign() -> None:
    assert parse_task("Купити пт фарбу", now=NOW).deadline is None


def test_tag_helpers() -> None:
    from app.bot.parser import normalize_tag, remove_tag, split_tags

    assert split_tags("Звіт #Бізнес !high #x\n#ignored") == ["Бізнес", "x"]
    assert remove_tag("Звіт #Бізнес !high", "Бізнес") == "Звіт !high"
    assert normalize_tag("Мій Бізнес") == normalize_tag("#мій_бізнес") == "мійбізнес"


@pytest.mark.parametrize(
    ("text", "rule", "deadline"),
    [
        ("Зал щодня о 18:00", "FREQ=DAILY", datetime(2026, 11, 3, 18, 0, tzinfo=TIMEZONE)),
        ("Вітаміни @щодня о 9:00", "FREQ=DAILY", datetime(2026, 11, 4, 9, 0, tzinfo=TIMEZONE)),
        ("Звіт щоп'ятниці", "FREQ=WEEKLY;BYDAY=FR", datetime(2026, 11, 6, 23, 59, tzinfo=TIMEZONE)),
        ("Планування @щопн о 10:00", "FREQ=WEEKLY;BYDAY=MO", datetime(2026, 11, 9, 10, 0, tzinfo=TIMEZONE)),
        ("Стендап по буднях о 9:30", "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", datetime(2026, 11, 4, 9, 30, tzinfo=TIMEZONE)),
        ("Оренда щомісяця 05.12", "FREQ=MONTHLY", datetime(2026, 12, 5, 23, 59, tzinfo=TIMEZONE)),
    ],
)
def test_recurrence_markers(text: str, rule: str, deadline: datetime) -> None:
    parsed = parse_task(text, now=NOW)
    assert parsed.recurrence == rule
    assert parsed.deadline == deadline
    assert parsed.title in {"Зал", "Вітаміни", "Звіт", "Планування", "Стендап", "Оренда"}

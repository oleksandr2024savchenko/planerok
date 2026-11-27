from datetime import date, datetime, time

from app.config import TIMEZONE
from app.models import NotificationPrefs, Priority
from app.services.digest import DigestData, DigestItem, is_due, render_digest

NOW = datetime(2026, 11, 27, 8, 5, tzinfo=TIMEZONE)


def _prefs(**kwargs) -> NotificationPrefs:
    defaults = {"user_id": 1, "digest_enabled": True, "digest_time": time(8, 0), "last_digest_on": None}
    return NotificationPrefs(**{**defaults, **kwargs})


def test_due_window() -> None:
    assert is_due(None, NOW)  # defaults: on, 08:00
    assert not is_due(None, NOW.replace(hour=7, minute=59))
    assert is_due(None, NOW.replace(hour=9, minute=59))  # catch-up after downtime
    assert not is_due(None, NOW.replace(hour=10, minute=0))
    assert not is_due(_prefs(digest_enabled=False), NOW)
    assert not is_due(_prefs(last_digest_on=date(2026, 11, 27)), NOW)
    assert is_due(_prefs(last_digest_on=date(2026, 11, 26)), NOW)
    assert not is_due(_prefs(digest_time=time(21, 30)), NOW)


def test_empty_digest_is_not_sent() -> None:
    assert render_digest(DigestData(first_name="Олена")) is None


def test_render_sections() -> None:
    data = DigestData(
        first_name="Олена",
        today=[
            DigestItem("Стендап", datetime(2026, 11, 27, 9, 30, tzinfo=TIMEZONE), Priority.MEDIUM, space="Бізнес"),
            DigestItem("Зал", datetime(2026, 11, 27, 18, 0, tzinfo=TIMEZONE), Priority.MEDIUM, streak=6, recurring=True),
            DigestItem("Оплатити <рахунок>", datetime(2026, 11, 27, 23, 59, tzinfo=TIMEZONE), Priority.HIGH),
        ],
        overdue=[DigestItem("Звіт", datetime(2026, 11, 25, 23, 59, tzinfo=TIMEZONE), Priority.MEDIUM)],
    )
    text = render_digest(data)
    assert text is not None
    assert text.startswith("☀️ Доброго ранку, Олена!")
    assert "📋 <b>Сьогодні · 3</b>" in text
    assert "• <b>09:30</b> Стендап · 📂 Бізнес" in text
    assert "• <b>18:00</b> Зал · 🔥 6" in text
    assert "• 🔺 Оплатити &lt;рахунок&gt;" in text  # date-only: no time, HTML escaped
    assert "⚠️ <b>Прострочені · 1</b>\n• <b>25.11</b> Звіт" in text
    assert "Не перервай серію: <b>Зал</b> — 6 поспіль" in text


def test_only_overdue_and_long_lists() -> None:
    overdue = [
        DigestItem(f"Задача {i}", datetime(2026, 11, 26, 10, 0, tzinfo=TIMEZONE), Priority.LOW) for i in range(12)
    ]
    text = render_digest(DigestData(first_name="", overdue=overdue))
    assert text is not None
    assert text.startswith("☀️ Доброго ранку!")
    assert "На сьогодні запланованого немає." in text
    assert "• <b>26.11 10:00</b> Задача 0" in text
    assert "…і ще 2" in text

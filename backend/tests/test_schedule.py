from datetime import datetime, timedelta

from app.config import TIMEZONE
from app.services.tasks import apply_schedule


def test_timed_deadline_becomes_one_hour_block() -> None:
    deadline = datetime(2026, 11, 4, 10, 0, tzinfo=TIMEZONE)
    payload = apply_schedule({"deadline": deadline, "start_time": None, "end_time": None})
    assert payload["start_time"] == deadline
    assert payload["end_time"] == deadline + timedelta(hours=1)


def test_end_of_day_deadline_does_not_become_a_block() -> None:
    deadline = datetime(2026, 11, 4, 23, 59, tzinfo=TIMEZONE)
    payload = apply_schedule({"deadline": deadline, "start_time": None, "end_time": None})
    assert payload["start_time"] is None
    assert payload["end_time"] is None


def test_explicit_start_fills_the_missing_end_and_deadline() -> None:
    start = datetime(2026, 11, 4, 9, 0, tzinfo=TIMEZONE)
    payload = apply_schedule({"start_time": start, "end_time": None, "deadline": None})
    assert payload["end_time"] == start + timedelta(hours=1)
    assert payload["deadline"] == payload["end_time"]


def test_explicit_block_is_left_alone() -> None:
    start = datetime(2026, 11, 4, 9, 0, tzinfo=TIMEZONE)
    end = datetime(2026, 11, 4, 9, 45, tzinfo=TIMEZONE)
    payload = apply_schedule({"start_time": start, "end_time": end, "deadline": start})
    assert payload["start_time"] == start
    assert payload["end_time"] == end
    assert payload["deadline"] == start

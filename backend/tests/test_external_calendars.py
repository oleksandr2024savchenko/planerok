from datetime import datetime

import pytest

from app.config import TIMEZONE
from app.services.external_calendars import (
    FeedError,
    assert_public_url,
    normalize_feed_url,
    parse_ics,
    stored_event_uids,
)

ICS = """BEGIN:VCALENDAR
PRODID:-//Planer//Test//UK
VERSION:2.0
X-WR-CALNAME:Зовнішній
BEGIN:VEVENT
UID:one-off
SUMMARY:Лекція
DTSTART:20261106T090000Z
DTEND:20261106T100000Z
END:VEVENT
BEGIN:VEVENT
UID:holiday
SUMMARY:Вихідний
DTSTART;VALUE=DATE:20261107
DTEND;VALUE=DATE:20261109
END:VEVENT
END:VCALENDAR
"""


def test_webcal_and_google_cid_become_https_ics() -> None:
    assert normalize_feed_url("webcal://example.com/basic.ics") == "https://example.com/basic.ics"
    link = normalize_feed_url(
        "https://calendar.google.com/calendar/u/0?cid=dWsudWtyYWluaWFuI2hvbGlkYXlAZ3JvdXAudi5jYWxlbmRhci5nb29nbGUuY29t"
    )
    assert link.startswith("https://calendar.google.com/calendar/ical/")
    assert link.endswith("/public/basic.ics")
    assert "uk.ukrainian%23holiday" in link


def test_private_targets_are_rejected() -> None:
    for url in (
        "http://127.0.0.1/cal.ics",
        "http://169.254.169.254/latest/meta-data",
        "https://10.0.0.8/secret.ics",
        "http://localhost/cal.ics",
        "https://calendar.example:8080/cal.ics",
    ):
        with pytest.raises(FeedError):
            assert_public_url(url)


RECURRING = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:lecture
SUMMARY:Пара
DTSTART:20261106T090000Z
DTEND:20261106T100000Z
RRULE:FREQ=DAILY;COUNT=3
END:VEVENT
END:VCALENDAR
"""


def test_occurrence_keys_stay_stable_and_distinct() -> None:
    now = datetime(2026, 11, 5, 12, 0, tzinfo=TIMEZONE)
    parsed = parse_ics(RECURRING.encode(), now=now)
    keys = [uid for _, uid in stored_event_uids(parsed.events)]
    assert len(keys) == 3
    assert len(set(keys)) == 3
    assert keys == [uid for _, uid in stored_event_uids(parse_ics(RECURRING.encode(), now=now).events)]
    done = {keys[0]}
    assert [uid in done for uid in keys] == [True, False, False]


def test_parse_timed_and_all_day_events() -> None:
    parsed = parse_ics(ICS.encode(), now=datetime(2026, 11, 5, 12, 0, tzinfo=TIMEZONE))
    assert parsed.name == "Зовнішній"
    titles = [(event.title, event.all_day, event.start.date().isoformat()) for event in parsed.events]
    assert ("Лекція", False, "2026-11-06") in titles
    assert ("Вихідний", True, "2026-11-07") in titles
    assert ("Вихідний", True, "2026-11-08") in titles
    assert all(item[2] != "2026-11-09" or item[0] != "Вихідний" for item in titles)

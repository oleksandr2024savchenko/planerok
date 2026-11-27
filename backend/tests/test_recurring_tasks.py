"""Recurring tasks and streaks through the API (needs TEST_DATABASE_URL)."""

from datetime import datetime, timedelta

import pytest

from app.config import TIMEZONE
from app.services import tasks as tasks_service
from tests.test_spaces_isolation import (  # noqa: F401 - shared fixtures
    ALICE,
    BOB,
    TEST_DATABASE_URL,
    _auth,
    anyio_backend,
    client,
    session_factory,
)

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
]

NOW = datetime(2026, 11, 3, 7, 0, tzinfo=TIMEZONE)  # Tuesday


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    clock = [NOW]
    monkeypatch.setattr(tasks_service, "now", lambda: clock[0])
    return clock


async def _open_tasks(client, telegram_id: int) -> list[dict]:  # noqa: F811
    tasks = (await client.get("/tasks", headers=_auth(telegram_id))).json()
    return [t for t in tasks if not t["is_completed"]]


async def test_completing_daily_task_creates_next_and_counts_streak(client, frozen_now) -> None:  # noqa: F811
    created = await client.post(
        "/tasks",
        json={"title": "Зал", "recurrence": "freq=daily", "deadline": "2026-11-03T08:00:00+01:00"},
        headers=_auth(ALICE),
    )
    assert created.status_code == 201
    task = created.json()
    assert (task["recurrence_rule"], task["recurrence_label"], task["streak_current"]) == ("FREQ=DAILY", "щодня", 0)

    done = (await client.patch(f"/tasks/{task['id']}", json={"is_completed": True}, headers=_auth(ALICE))).json()
    assert (done["streak_current"], done["streak_best"]) == (1, 1)

    [following] = await _open_tasks(client, ALICE)
    assert following["title"] == "Зал"
    assert following["deadline"].startswith("2026-11-04T08:00")
    assert following["recurrence_rule"] == "FREQ=DAILY"

    # Done on time the next day: streak grows.
    frozen_now[0] = NOW + timedelta(days=1)
    done = (await client.patch(f"/tasks/{following['id']}", json={"status": "done"}, headers=_auth(ALICE))).json()
    assert done["streak_current"] == 2

    # Skip two days, then finish late: streak restarts, missed days are not recreated.
    [third] = await _open_tasks(client, ALICE)
    frozen_now[0] = NOW + timedelta(days=4, hours=12)
    done = (await client.patch(f"/tasks/{third['id']}", json={"is_completed": True}, headers=_auth(ALICE))).json()
    assert (done["streak_current"], done["streak_best"]) == (1, 2)
    [fourth] = await _open_tasks(client, ALICE)
    assert fourth["deadline"].startswith("2026-11-08T08:00")


async def test_recurring_without_date_starts_on_first_matching_day(client) -> None:  # noqa: F811
    task = (
        await client.post("/tasks", json={"title": "Звіт", "recurrence": "FREQ=WEEKLY;BYDAY=FR"}, headers=_auth(ALICE))
    ).json()
    assert task["deadline"].startswith("2026-11-06T23:59")
    assert task["recurrence_label"] == "щотижня (пт)"


async def test_reopening_and_recompleting_does_not_duplicate(client) -> None:  # noqa: F811
    task_id = (
        await client.post("/tasks", json={"title": "Вітаміни", "recurrence": "FREQ=DAILY"}, headers=_auth(ALICE))
    ).json()["id"]
    for completed in (True, False, True):
        await client.patch(f"/tasks/{task_id}", json={"is_completed": completed}, headers=_auth(ALICE))
    assert len(await _open_tasks(client, ALICE)) == 1


async def test_stop_series_and_delete(client) -> None:  # noqa: F811
    task_id = (
        await client.post("/tasks", json={"title": "Біг", "recurrence": "FREQ=DAILY"}, headers=_auth(ALICE))
    ).json()["id"]
    stopped = (await client.patch(f"/tasks/{task_id}", json={"recurrence": None}, headers=_auth(ALICE))).json()
    assert stopped["recurrence_rule"] is None
    await client.patch(f"/tasks/{task_id}", json={"is_completed": True}, headers=_auth(ALICE))
    assert await _open_tasks(client, ALICE) == []

    other = (
        await client.post("/tasks", json={"title": "Йога", "recurrence": "FREQ=DAILY"}, headers=_auth(ALICE))
    ).json()["id"]
    await client.delete(f"/tasks/{other}", headers=_auth(ALICE))
    assert await _open_tasks(client, ALICE) == []


async def test_invalid_rule_is_rejected(client) -> None:  # noqa: F811
    response = await client.post("/tasks", json={"title": "x", "recurrence": "FREQ=YEARLY"}, headers=_auth(ALICE))
    assert response.status_code == 422


async def test_next_occurrence_stays_in_shared_space(client, session_factory) -> None:  # noqa: F811
    from app.models import SpaceRole
    from tests.test_spaces_isolation import _share_space

    shared = await _share_space(session_factory, {ALICE: SpaceRole.OWNER, BOB: SpaceRole.EDITOR})
    task_id = (
        await client.post(
            "/tasks", json={"title": "Смітник", "recurrence": "FREQ=DAILY", "space_id": shared}, headers=_auth(ALICE)
        )
    ).json()["id"]
    await client.patch(f"/tasks/{task_id}", json={"is_completed": True}, headers=_auth(BOB))
    [following] = await _open_tasks(client, BOB)
    assert following["space_id"] == shared

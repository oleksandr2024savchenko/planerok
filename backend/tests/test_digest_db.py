"""Digest collection, sending and settings against PostgreSQL (needs TEST_DATABASE_URL)."""

from datetime import datetime, timedelta

import pytest

from app import scheduler
from app.config import TIMEZONE
from app.models import SpaceRole
from app.services import digest as digest_service
from app.services import users as users_service
from tests.test_spaces_isolation import (  # noqa: F401 - shared fixtures
    ALICE,
    BOB,
    TEST_DATABASE_URL,
    _auth,
    _share_space,
    anyio_backend,
    client,
    session_factory,
)

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
]


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def test_collect_digest_respects_spaces_and_status(client, session_factory) -> None:  # noqa: F811
    now = datetime.now(TIMEZONE)
    today_at = now.replace(hour=23, minute=0, second=0, microsecond=0)
    yesterday = today_at - timedelta(days=1)
    shared = await _share_space(session_factory, {ALICE: SpaceRole.OWNER, BOB: SpaceRole.EDITOR})

    async def add(who: int, title: str, **extra) -> int:
        response = await client.post("/tasks", json={"title": title, **extra}, headers=_auth(who))
        assert response.status_code == 201, response.text
        return response.json()["id"]

    await add(ALICE, "Сьогодні моє", deadline=_iso(today_at))
    await add(ALICE, "Прострочене", deadline=_iso(yesterday))
    await add(ALICE, "Беклог", deadline=_iso(today_at), status="backlog")
    await add(ALICE, "Без дати")
    await add(ALICE, "Завтра", deadline=_iso(today_at + timedelta(days=1)))
    done = await add(ALICE, "Вже зроблено", deadline=_iso(today_at))
    await client.patch(f"/tasks/{done}", json={"is_completed": True}, headers=_auth(ALICE))
    gone = await add(ALICE, "Видалене", deadline=_iso(today_at))
    await client.delete(f"/tasks/{gone}", headers=_auth(ALICE))
    await add(BOB, "Секрет Боба", deadline=_iso(today_at))
    await add(BOB, "Спільне", deadline=_iso(today_at), space_id=shared)

    async with session_factory() as session:
        alice = await users_service.get_or_create_telegram_user(session, ALICE)
        data = await digest_service.collect_digest(session, alice, now)

    assert {(item.title, item.space) for item in data.today} == {("Сьогодні моє", None), ("Спільне", "Спільне")}
    assert [item.title for item in data.overdue] == ["Прострочене"]


async def test_send_due_digests_once_per_day(client, session_factory, monkeypatch) -> None:  # noqa: F811
    now = datetime.now(TIMEZONE)
    await client.post(
        "/tasks", json={"title": "Задача дня", "deadline": _iso(now.replace(hour=23, minute=0))}, headers=_auth(ALICE)
    )
    send_at = (now - timedelta(minutes=1)).strftime("%H:%M")
    if now.hour == 0 and now.minute < 2:
        pytest.skip("too close to midnight")
    response = await client.patch("/me/notifications", json={"digest_time": send_at}, headers=_auth(ALICE))
    assert response.json() == {"digest_enabled": True, "digest_time": send_at}
    # Bob has the default 08:00 digest, which may or may not be due right now; switch it off.
    await client.patch("/me/notifications", json={"digest_enabled": False}, headers=_auth(BOB))

    sent: list[tuple[int, str]] = []

    class FakeBot:
        async def send_message(self, chat_id: int, text: str) -> None:
            sent.append((chat_id, text))

    monkeypatch.setattr(scheduler, "_bot", FakeBot())
    monkeypatch.setattr(scheduler, "session_factory", session_factory)

    await scheduler.send_due_digests()
    await scheduler.send_due_digests()

    assert [chat for chat, _ in sent] == [ALICE]
    assert "Задача дня" in sent[0][1]


async def test_notification_settings_validation(client) -> None:  # noqa: F811
    assert (await client.get("/me/notifications", headers=_auth(ALICE))).json() == {
        "digest_enabled": True,
        "digest_time": "08:00",
    }
    off = await client.patch("/me/notifications", json={"digest_enabled": False}, headers=_auth(ALICE))
    assert off.json()["digest_enabled"] is False
    assert (await client.patch("/me/notifications", json={"digest_time": "25:00"}, headers=_auth(ALICE))).status_code == 422
    assert (await client.patch("/me/notifications", json={"digest_time": None}, headers=_auth(ALICE))).status_code == 422

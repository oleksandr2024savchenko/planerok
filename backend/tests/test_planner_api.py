"""Spaces CRUD, #space routing, task statuses and soft delete (needs TEST_DATABASE_URL)."""

import pytest
from sqlalchemy import select

from app.models import Task
from app.services import users as users_service
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


async def test_space_crud(client) -> None:  # noqa: F811
    created = await client.post("/spaces", json={"name": "Бізнес", "color": "#a855f7"}, headers=_auth(ALICE))
    assert created.status_code == 201
    space = created.json()
    assert (space["kind"], space["role"]) == ("shared", "owner")

    duplicate = await client.post("/spaces", json={"name": "бізнес"}, headers=_auth(ALICE))
    assert duplicate.status_code == 409
    # Names are per user.
    assert (await client.post("/spaces", json={"name": "Бізнес"}, headers=_auth(BOB))).status_code == 201

    renamed = await client.patch(f"/spaces/{space['id']}", json={"name": "Робота"}, headers=_auth(ALICE))
    assert renamed.json()["name"] == "Робота"
    assert (await client.patch(f"/spaces/{space['id']}", json={"name": "x"}, headers=_auth(BOB))).status_code == 404

    personal = next(s for s in (await client.get("/spaces", headers=_auth(ALICE))).json() if s["kind"] == "personal")
    assert (await client.delete(f"/spaces/{personal['id']}", headers=_auth(ALICE))).status_code == 400
    assert (await client.delete(f"/spaces/{space['id']}", headers=_auth(BOB))).status_code == 404

    await client.post("/tasks", json={"title": "У просторі", "space_id": space["id"]}, headers=_auth(ALICE))
    assert (await client.delete(f"/spaces/{space['id']}", headers=_auth(ALICE))).status_code == 204
    names = [s["name"] for s in (await client.get("/spaces", headers=_auth(ALICE))).json()]
    assert names == ["Особисте"]
    # Tasks of a deleted space disappear with it.
    assert (await client.get("/tasks", headers=_auth(ALICE))).json() == []


async def test_space_tag_routes_to_own_writable_space(client, session_factory) -> None:  # noqa: F811
    await client.post("/spaces", json={"name": "Мій Бізнес"}, headers=_auth(ALICE))
    async with session_factory() as session:
        alice = await users_service.get_or_create_telegram_user(session, ALICE)
        bob = await users_service.get_or_create_telegram_user(session, BOB)

        space, text = await users_service.resolve_space_tag(session, alice.id, "Звіт #мійбізнес !high @завтра")
        assert space is not None and space.name == "Мій Бізнес"
        assert text == "Звіт !high @завтра"

        space, text = await users_service.resolve_space_tag(session, alice.id, "Зал #тренування")
        assert space is None and text == "Зал #тренування"

        # Bob cannot route into Alice's space by guessing its name.
        space, _ = await users_service.resolve_space_tag(session, bob.id, "Звіт #МійБізнес")
        assert space is None


async def test_status_and_completion_stay_in_sync(client) -> None:  # noqa: F811
    task = (await client.post("/tasks", json={"title": "Задача"}, headers=_auth(ALICE))).json()
    assert (task["status"], task["is_completed"]) == ("todo", False)

    doing = await client.patch(f"/tasks/{task['id']}", json={"status": "doing"}, headers=_auth(ALICE))
    assert (doing.json()["status"], doing.json()["is_completed"]) == ("doing", False)

    done = await client.patch(f"/tasks/{task['id']}", json={"is_completed": True}, headers=_auth(ALICE))
    assert (done.json()["status"], done.json()["is_completed"]) == ("done", True)

    reopened = await client.patch(f"/tasks/{task['id']}", json={"is_completed": False}, headers=_auth(ALICE))
    assert (reopened.json()["status"], reopened.json()["is_completed"]) == ("todo", False)

    backlog = await client.post("/tasks", json={"title": "Колись", "status": "backlog"}, headers=_auth(ALICE))
    assert backlog.json()["status"] == "backlog"
    only_backlog = (await client.get("/tasks", params={"status": "backlog"}, headers=_auth(ALICE))).json()
    assert [t["title"] for t in only_backlog] == ["Колись"]


async def test_delete_is_soft(client, session_factory) -> None:  # noqa: F811
    task_id = (await client.post("/tasks", json={"title": "Тимчасова"}, headers=_auth(ALICE))).json()["id"]
    assert (await client.delete(f"/tasks/{task_id}", headers=_auth(ALICE))).status_code == 204

    assert (await client.get("/tasks", headers=_auth(ALICE))).json() == []
    assert (await client.patch(f"/tasks/{task_id}", json={"title": "x"}, headers=_auth(ALICE))).status_code == 404
    async with session_factory() as session:
        row = await session.scalar(select(Task).where(Task.id == task_id))
        assert row is not None and row.deleted_at is not None


async def test_move_task_between_spaces(client) -> None:  # noqa: F811
    task_id = (await client.post("/tasks", json={"title": "Перенести"}, headers=_auth(ALICE))).json()["id"]
    alice_space = (await client.post("/spaces", json={"name": "Дім"}, headers=_auth(ALICE))).json()["id"]
    bob_space = (await client.post("/spaces", json={"name": "Боб"}, headers=_auth(BOB))).json()["id"]

    moved = await client.patch(f"/tasks/{task_id}", json={"space_id": alice_space}, headers=_auth(ALICE))
    assert moved.json()["space_id"] == alice_space
    foreign = await client.patch(f"/tasks/{task_id}", json={"space_id": bob_space}, headers=_auth(ALICE))
    assert foreign.status_code == 403

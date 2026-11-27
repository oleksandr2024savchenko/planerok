"""Data isolation between users and spaces.

Runs against a real PostgreSQL database given in TEST_DATABASE_URL, e.g.
postgresql+asyncpg://postgres@127.0.0.1:5432/planer_test (the schema is recreated).
"""

import hashlib
import hmac
import json
import os
import time
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import api_router
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Base, Space, SpaceKind, SpaceMember, SpaceRole
from app.services import users as users_service

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
BOT_TOKEN = "123456:TEST"

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
]

ALICE, BOB = 1001, 2002


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(TEST_DATABASE_URL)  # type: ignore[arg-type]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    app.include_router(api_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_settings] = lambda: Settings(bot_token=BOT_TOKEN, dev_user_id=None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _auth(telegram_id: int, first_name: str = "Тест") -> dict[str, str]:
    fields = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": telegram_id, "first_name": first_name}, ensure_ascii=False),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {"X-Telegram-Init-Data": urlencode(fields)}


async def _share_space(
    session_factory: async_sessionmaker[AsyncSession], telegram_ids: dict[int, SpaceRole]
) -> int:
    async with session_factory() as session:
        space = Space(name="Спільне", kind=SpaceKind.SHARED)
        session.add(space)
        await session.flush()
        for telegram_id, role in telegram_ids.items():
            user = await users_service.get_or_create_telegram_user(session, telegram_id)
            session.add(SpaceMember(space_id=space.id, user_id=user.id, role=role))
        await session.commit()
        return space.id


async def test_first_sign_in_creates_user_with_personal_space(client: httpx.AsyncClient) -> None:
    me = (await client.get("/me", headers=_auth(ALICE, "Аліса"))).json()
    assert me["display_name"] == "Аліса"
    assert me["base_currency"] == "EUR"
    assert me["id"] != ALICE  # internal id, not the Telegram id

    spaces = (await client.get("/spaces", headers=_auth(ALICE))).json()
    assert [(s["name"], s["kind"], s["role"]) for s in spaces] == [("Особисте", "personal", "owner")]

    again = (await client.get("/me", headers=_auth(ALICE))).json()
    assert again["id"] == me["id"]


async def test_users_do_not_see_each_others_tasks(client: httpx.AsyncClient) -> None:
    created = await client.post("/tasks", json={"title": "Секрет Аліси"}, headers=_auth(ALICE))
    assert created.status_code == 201
    task_id = created.json()["id"]

    assert (await client.get("/tasks", headers=_auth(BOB))).json() == []
    assert (await client.patch(f"/tasks/{task_id}", json={"title": "x"}, headers=_auth(BOB))).status_code == 404
    assert (await client.delete(f"/tasks/{task_id}", headers=_auth(BOB))).status_code == 404

    alice_space = created.json()["space_id"]
    foreign = await client.post("/tasks", json={"title": "y", "space_id": alice_space}, headers=_auth(BOB))
    assert foreign.status_code == 403

    titles = [t["title"] for t in (await client.get("/tasks", headers=_auth(ALICE))).json()]
    assert titles == ["Секрет Аліси"]


async def test_shared_space_is_visible_to_both_members(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/tasks", json={"title": "Особисте Аліси"}, headers=_auth(ALICE))
    await client.post("/tasks", json={"title": "Особисте Боба"}, headers=_auth(BOB))
    shared = await _share_space(session_factory, {ALICE: SpaceRole.OWNER, BOB: SpaceRole.EDITOR})

    created = await client.post("/tasks", json={"title": "Купити квитки", "space_id": shared}, headers=_auth(BOB))
    assert created.status_code == 201

    alice_titles = {t["title"] for t in (await client.get("/tasks", headers=_auth(ALICE))).json()}
    bob_titles = {t["title"] for t in (await client.get("/tasks", headers=_auth(BOB))).json()}
    assert alice_titles == {"Особисте Аліси", "Купити квитки"}
    assert bob_titles == {"Особисте Боба", "Купити квитки"}

    task_id = created.json()["id"]
    updated = await client.patch(f"/tasks/{task_id}", json={"is_completed": True}, headers=_auth(ALICE))
    assert updated.status_code == 200


async def test_viewer_can_read_but_not_write(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    shared = await _share_space(session_factory, {ALICE: SpaceRole.OWNER, BOB: SpaceRole.VIEWER})
    task_id = (await client.post("/tasks", json={"title": "План", "space_id": shared}, headers=_auth(ALICE))).json()[
        "id"
    ]

    assert [t["title"] for t in (await client.get("/tasks", headers=_auth(BOB))).json()] == ["План"]
    assert (await client.patch(f"/tasks/{task_id}", json={"title": "x"}, headers=_auth(BOB))).status_code == 404
    assert (await client.delete(f"/tasks/{task_id}", headers=_auth(BOB))).status_code == 404
    write = await client.post("/tasks", json={"title": "z", "space_id": shared}, headers=_auth(BOB))
    assert write.status_code == 403


async def test_requests_without_valid_init_data_are_rejected(client: httpx.AsyncClient) -> None:
    assert (await client.get("/tasks")).status_code == 401
    forged = {"X-Telegram-Init-Data": _auth(ALICE)["X-Telegram-Init-Data"].replace("hash=", "hash=0")}
    assert (await client.get("/tasks", headers=forged)).status_code == 401

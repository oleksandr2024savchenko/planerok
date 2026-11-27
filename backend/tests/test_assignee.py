"""Tasks written for each other: «Мені», «Партнеру», «Разом»."""

import asyncio

import pytest

from app.models import Priority, Task, User
from app.schemas import Assignee, TaskCreate, TaskRead, TaskUpdate
from app.services import tasks as tasks_service

ME, HER = 969740172, 729424163


class _Session:
    def __init__(self, *objects) -> None:
        self.users = {u.telegram_id: u for u in objects if isinstance(u, User)}
        self.tasks = {t.id: t for t in objects if isinstance(t, Task)}

    async def get(self, model, key):
        return (self.users if model is User else self.tasks).get(key)


def _couple() -> _Session:
    return _Session(
        User(telegram_id=ME, partner_telegram_id=HER, first_name="Саша"),
        User(telegram_id=HER, partner_telegram_id=ME, first_name="Таня"),
    )


def _task(**kw) -> Task:
    base = dict(id=1, user_id=ME, owner_id=ME, created_by_id=ME, title="Купити квіти", priority=Priority.MEDIUM,
                is_shared=False, assigned_to_id=None, is_completed=False)
    base.update(kw)
    return Task(**base)


def _apply(session, task, assignee, actor):
    asyncio.run(tasks_service._apply_assignee(session, task, Assignee(assignee), actor))
    return task


def test_hand_task_to_partner() -> None:
    task = _apply(_couple(), _task(), "partner", ME)
    assert (task.owner_id, task.user_id, task.assigned_to_id, task.is_shared) == (HER, HER, HER, False)
    assert task.created_by_id == ME  # the author keeps seeing it


def test_take_task_back_and_share() -> None:
    session = _couple()
    task = _apply(session, _task(owner_id=HER, user_id=HER, assigned_to_id=HER), "me", ME)
    assert (task.owner_id, task.assigned_to_id) == (ME, None)
    task = _apply(session, task, "shared", ME)
    assert task.is_shared and task.owner_id == ME and task.assigned_to_id is None


def test_partner_sees_from_her_side() -> None:
    # She opens a task I gave her and picks «Мені»: it stays hers.
    task = _apply(_couple(), _task(owner_id=HER, user_id=HER, assigned_to_id=HER), "me", HER)
    assert (task.owner_id, task.assigned_to_id, task.is_shared) == (HER, None, False)


def test_shared_keeps_existing_owner_of_the_couple() -> None:
    task = _apply(_couple(), _task(owner_id=HER, user_id=HER), "shared", ME)
    assert task.is_shared and task.owner_id == HER


def test_author_and_assignee_both_see_the_task() -> None:
    session = _couple()
    task = _task(owner_id=HER, user_id=HER, assigned_to_id=HER, created_by_id=ME)
    session.tasks[task.id] = task
    assert asyncio.run(tasks_service.get_task(session, ME, 1)) is task
    assert asyncio.run(tasks_service.get_task(session, HER, 1)) is task


def test_private_task_stays_private() -> None:
    session = _couple()
    task = _task(owner_id=HER, user_id=HER, created_by_id=HER)
    session.tasks[task.id] = task
    assert asyncio.run(tasks_service.get_task(session, ME, 1)) is None


def test_schemas_accept_assignee() -> None:
    assert TaskCreate(title="x", assignee="partner").assignee is Assignee.PARTNER
    assert TaskUpdate(assignee="shared").model_dump(exclude_unset=True) == {"assignee": Assignee.SHARED}
    with pytest.raises(ValueError):
        TaskCreate(title="x", assignee="кіт")
    assert "created_by_id" in TaskRead.model_fields


def test_names_are_filled_from_telegram_once() -> None:
    from types import SimpleNamespace

    from app.services.users import fill_names_from_telegram

    asked: list[int] = []

    class _Bot:
        async def get_chat(self, chat_id: int):
            asked.append(chat_id)
            if chat_id == ME:
                return SimpleNamespace(first_name="Саша")
            raise RuntimeError("chat not found")

    class _Commit:
        async def commit(self) -> None:
            return None

    me, her, known = User(telegram_id=ME), User(telegram_id=HER), User(telegram_id=1, first_name="Вже є")
    asyncio.run(fill_names_from_telegram(_Commit(), _Bot(), [me, her, known]))
    assert me.first_name == "Саша"
    assert her.first_name is None  # Telegram refused: stay unnamed, no crash
    assert asked == [ME, HER]  # a known name is not asked again


class _EditSession(_Session):
    async def commit(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None


def _edit(monkeypatch, task, update, actor):
    told: list[tuple[int, bool]] = []

    async def notify(t, actor_id):
        told.append((actor_id, t.is_shared))

    monkeypatch.setattr(tasks_service.scheduler, "notify_assigned", notify)
    monkeypatch.setattr(tasks_service, "sync_reminder", lambda t: None)
    session = _EditSession(*_couple().users.values())
    asyncio.run(tasks_service.update_task(session, task, update, push_google=False, actor_id=actor))
    return told


def test_making_a_task_shared_tells_the_partner(monkeypatch) -> None:
    assert _edit(monkeypatch, _task(), TaskUpdate(assignee="shared"), ME) == [(ME, True)]
    # The old toggle field counts too.
    assert _edit(monkeypatch, _task(), TaskUpdate(is_shared=True), HER) == [(HER, True)]


def test_plain_edits_stay_quiet(monkeypatch) -> None:
    assert _edit(monkeypatch, _task(is_shared=True), TaskUpdate(title="Інша назва"), ME) == []
    assert _edit(monkeypatch, _task(), TaskUpdate(title="Інша назва"), ME) == []


def test_giving_a_task_away_still_tells_the_partner(monkeypatch) -> None:
    assert _edit(monkeypatch, _task(), TaskUpdate(assignee="partner"), ME) == [(ME, False)]


def test_creating_a_shared_task_tells_the_partner(monkeypatch) -> None:
    told: list[bool] = []

    async def notify(t, actor_id):
        told.append(t.is_shared)

    class _CreateSession(_EditSession):
        def add(self, obj) -> None:
            obj.id = 99

    monkeypatch.setattr(tasks_service.scheduler, "notify_assigned", notify)
    monkeypatch.setattr(tasks_service, "sync_reminder", lambda t: None)
    session = _CreateSession(*_couple().users.values())
    asyncio.run(tasks_service.create_task(session, ME, TaskCreate(title="Кіно", assignee="shared"), push_google=False))
    asyncio.run(tasks_service.create_task(session, ME, TaskCreate(title="Сам", assignee="me"), push_google=False))
    assert told == [True]  # shared → partner hears about it; a private task stays quiet


def _delete(monkeypatch, task, actor):
    told: list[tuple[str, set[int], int]] = []

    async def notify(title, recipients, actor_id):
        told.append((title, recipients, actor_id))

    class _DeleteSession(_EditSession):
        async def delete(self, _obj) -> None:
            return None

    monkeypatch.setattr(tasks_service.scheduler, "notify_cancelled", notify)
    monkeypatch.setattr(tasks_service.scheduler, "cancel_reminder", lambda _id: None)
    session = _DeleteSession(*_couple().users.values())
    asyncio.run(tasks_service.delete_task(session, task, push_google=False, actor_id=actor))
    return told


def test_cancelling_a_shared_task_tells_the_partner(monkeypatch) -> None:
    assert _delete(monkeypatch, _task(is_shared=True), ME) == [("Купити квіти", {HER}, ME)]


def test_cancelling_a_task_given_to_me_tells_its_author(monkeypatch) -> None:
    task = _task(owner_id=HER, user_id=HER, assigned_to_id=HER, created_by_id=ME)
    assert _delete(monkeypatch, task, HER) == [("Купити квіти", {ME}, HER)]


def test_cancelling_my_own_task_is_quiet(monkeypatch) -> None:
    assert _delete(monkeypatch, _task(), ME) == [("Купити квіти", set(), ME)]

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

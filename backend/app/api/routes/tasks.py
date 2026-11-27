from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import SessionDep, CurrentUserDep
from app.models import Task, TaskStatus
from app.services import users as users_service
from app.schemas import TaskCreate, TaskRead, TaskScope, TaskUpdate
from app.services import tasks as tasks_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _get_writable_task(session: SessionDep, user_id: int, task_id: int) -> Task:
    task = await tasks_service.get_task(session, user_id, task_id, write=True)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    session: SessionDep,
    user: CurrentUserDep,
    scope: TaskScope = TaskScope.ALL,
    category: str | None = None,
    space_id: int | None = None,
    status: TaskStatus | None = None,
) -> list[Task]:
    return list(
        await tasks_service.list_tasks(
            session, user.id, scope=scope, category=category, space_id=space_id, status=status
        )
    )


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, session: SessionDep, user: CurrentUserDep) -> Task:
    try:
        return await tasks_service.create_task(session, user.id, payload)
    except tasks_service.SpaceAccessError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No write access to this space") from exc


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(task_id: int, payload: TaskUpdate, session: SessionDep, user: CurrentUserDep) -> Task:
    task = await _get_writable_task(session, user.id, task_id)
    if payload.space_id is not None and not await users_service.can_write(session, user.id, payload.space_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No write access to the target space")
    return await tasks_service.update_task(session, task, payload)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, session: SessionDep, user: CurrentUserDep) -> Response:
    task = await _get_writable_task(session, user.id, task_id)
    await tasks_service.delete_task(session, task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

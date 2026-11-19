from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import SessionDep, UserIdDep
from app.models import Task
from app.schemas import TaskCreate, TaskRead, TaskScope, TaskUpdate
from app.services import tasks as tasks_service
from app.services.external_calendars import events_for, set_event_completed

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _get_owned_task(session: SessionDep, user_id: int, task_id: int) -> Task:
    task = await tasks_service.get_task(session, user_id, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    session: SessionDep,
    user_id: UserIdDep,
    scope: TaskScope = TaskScope.ALL,
    category: str | None = None,
) -> list[TaskRead]:
    tasks = [TaskRead.model_validate(task) for task in await tasks_service.list_tasks(session, user_id, scope=scope, category=category)]
    if category:
        return tasks
    tasks.extend(await events_for(session, user_id, scope))
    return tasks


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, session: SessionDep, user_id: UserIdDep) -> Task:
    return await tasks_service.create_task(session, user_id, payload)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(task_id: int, payload: TaskUpdate, session: SessionDep, user_id: UserIdDep) -> Task | TaskRead:
    if task_id < 0:
        # Subscribed calendar events use negative ids and can only be checked off.
        if payload.model_fields_set != {"is_completed"} or payload.is_completed is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Подію з календаря можна лише позначити виконаною")
        updated = await set_event_completed(session, user_id, -task_id, payload.is_completed)
        if updated is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Подію не знайдено")
        return updated
    task = await _get_owned_task(session, user_id, task_id)
    return await tasks_service.update_task(session, task, payload, actor_id=user_id)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, session: SessionDep, user_id: UserIdDep) -> Response:
    task = await _get_owned_task(session, user_id, task_id)
    await tasks_service.delete_task(session, task, actor_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

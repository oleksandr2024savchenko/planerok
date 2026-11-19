"""Focus timer API. Lives under /tasks so Caddy already routes it to the backend."""

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import SessionDep, UserIdDep
from app.models import Task, TaskTimer
from app.schemas import TimerRead, TimerStart
from app.services import tasks as tasks_service
from app.services import timers

router = APIRouter(prefix="/tasks/timer", tags=["timer"])


async def _read(session: SessionDep, timer: TaskTimer) -> TimerRead:
    task = await session.get(Task, timer.task_id)
    at = timers.now()
    return TimerRead(
        id=timer.id,
        task_id=timer.task_id,
        task_title=task.title if task else "Задача",
        kind=timer.kind,
        status=timer.status,
        duration_seconds=timer.duration_seconds,
        remaining_seconds=timers.remaining(timer, at),
        task_focused_seconds=(task.focused_seconds or 0) if task else 0,
        server_now=at,
    )


async def _live(session: SessionDep, user_id: int) -> TaskTimer:
    timer = await timers.active_timer(session, user_id)
    if timer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Таймер не запущено")
    return timer


@router.get("", response_model=TimerRead | None)
async def current_timer(session: SessionDep, user_id: UserIdDep) -> TimerRead | None:
    timer = await timers.active_timer(session, user_id)
    return await _read(session, timer) if timer else None


@router.post("", response_model=TimerRead, status_code=status.HTTP_201_CREATED)
async def start_timer(payload: TimerStart, session: SessionDep, user_id: UserIdDep) -> TimerRead:
    task = await tasks_service.get_task(session, user_id, payload.task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задачу не знайдено")
    timer = await timers.start(session, user_id, task, payload.minutes, kind=payload.kind)
    return await _read(session, timer)


@router.post("/pause", response_model=TimerRead)
async def pause_timer(session: SessionDep, user_id: UserIdDep) -> TimerRead:
    return await _read(session, await timers.pause(session, await _live(session, user_id)))


@router.post("/resume", response_model=TimerRead)
async def resume_timer(session: SessionDep, user_id: UserIdDep) -> TimerRead:
    return await _read(session, await timers.resume(session, await _live(session, user_id)))


@router.post("/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_timer(session: SessionDep, user_id: UserIdDep) -> Response:
    await timers.stop(session, await _live(session, user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

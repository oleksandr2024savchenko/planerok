"""Timetable PDF import. Under /tasks so Caddy routes it to the backend."""

import base64
import binascii

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app import scheduler
from app.api.deps import SessionDep, UserIdDep
from app.schemas import Assignee, ScheduleEvent, ScheduleImport, ScheduleImportResult, SchedulePdf, SchedulePreview
from app.services import schedule_import
from app.services.ai_agent import TaskExtractionError

router = APIRouter(prefix="/tasks/import", tags=["import"])


@router.post("/pdf", response_model=SchedulePreview)
async def preview_pdf(payload: SchedulePdf, user_id: UserIdDep) -> SchedulePreview:
    """Read the PDF and return the events found. Nothing is saved yet."""
    try:
        pdf = base64.b64decode(payload.file_base64.split(",")[-1], validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл пошкоджено") from exc
    try:
        title, occurrences = await schedule_import.read_pdf(pdf)
    except TaskExtractionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return SchedulePreview(
        title=title,
        events=[ScheduleEvent(title=o.title, start=o.start, end=o.end, description=o.description) for o in occurrences],
    )


@router.post("", response_model=ScheduleImportResult)
async def import_events(
    payload: ScheduleImport,
    session: SessionDep,
    user_id: UserIdDep,
    background: BackgroundTasks,
) -> ScheduleImportResult:
    occurrences = [
        schedule_import.Occurrence(title=e.title.strip(), start=e.start, end=e.end, description=e.description)
        for e in payload.events
    ]
    created, skipped = await schedule_import.import_occurrences(
        session,
        user_id,
        occurrences,
        assignee=payload.assignee,
        category=payload.category,
        remind_before_minutes=payload.remind_before_minutes,
    )
    # Google calls take a while for dozens of lessons: answer now, mirror in the background.
    background.add_task(schedule_import.mirror_to_google, [task.id for task in created])
    if payload.assignee is not Assignee.ME:
        background.add_task(
            scheduler.notify_import,
            user_id,
            len(created),
            payload.title,
            shared=payload.assignee is Assignee.SHARED,
        )
    return ScheduleImportResult(created=len(created), skipped=skipped)

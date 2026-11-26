"""Timetable PDF → calendar events.

Gemini reads the PDF and lists lessons/shifts, either on a date or on a weekday. Weekly ones are
expanded here into concrete occurrences, so the planner and Google get ordinary timed tasks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from google.genai import types
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TIMEZONE
from app.models import Task
from app.schemas import Assignee, TaskCreate
from app.services.ai_agent import (
    TaskExtractionError,
    _failure_message,
    _generate,
    _safe_error,
)

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_EVENTS = 150
DEFAULT_WEEKS = 8
MAX_WEEKS = 16


class ScheduleItem(BaseModel):
    """One row of a timetable as Gemini reads it. Wire schema: plain strings, no formats."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Subject, lesson or shift name, without the time.")
    start: str = Field(description="Start time HH:MM, 24h.")
    end: str | None = Field(default=None, description="End time HH:MM, or null.")
    date: str | None = Field(default=None, description="YYYY-MM-DD for a one-off event, else null.")
    weekday: int | None = Field(default=None, description="1=Monday … 7=Sunday for a weekly event, else null.")
    every_weeks: int | None = Field(default=None, description="2 for every other week (чисельник/знаменник), else 1.")
    first_date: str | None = Field(default=None, description="YYYY-MM-DD of the first lesson when known.")
    until: str | None = Field(default=None, description="YYYY-MM-DD the weekly lesson stops, when known.")
    location: str | None = Field(default=None, description="Room, building or link.")
    note: str | None = Field(default=None, description="Teacher, type (лекція/практика), group.")


class ScheduleExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, description="Short name of the timetable, e.g. «Розклад КН-21».")
    items: list[ScheduleItem] = Field(default_factory=list)


@dataclass(slots=True)
class Occurrence:
    title: str
    start: datetime
    end: datetime
    description: str | None

    @property
    def key(self) -> str:
        return f"{self.start.isoformat()}|{self.title}"


def build_schedule_prompt(today: date) -> str:
    return (
        "Ти читаєш PDF з розкладом (пари, уроки, зміни на роботі, гуртки) і повертаєш усі заняття.\n"
        f"Сьогодні {today.isoformat()} (Europe/Vienna).\n"
        "Правила:\n"
        "- Кожне заняття — окремий елемент items. Не вигадуй того, чого немає у файлі.\n"
        "- Якщо в розкладі конкретна дата — заповни date. Якщо заняття повторюється щотижня за днем тижня — weekday "
        "(1=понеділок … 7=неділя), date=null.\n"
        "- «Чисельник/знаменник», «через тиждень», «непарні тижні» — every_weeks=2, і first_date, якщо зрозуміло.\n"
        "- Якщо вказано період семестру чи дати дії розкладу — until (і first_date, якщо початок пізніше сьогодні).\n"
        "- start/end — HH:MM у 24-годинному форматі. Якщо кінця немає — end=null.\n"
        "- title — назва предмета/зміни; location — аудиторія чи посилання; note — викладач, тип заняття, група.\n"
        "- Відповідь — лише JSON {\"title\", \"items\":[...]}."
    )


def _clock(value: str | None) -> time | None:
    if not value:
        return None
    try:
        hours, minutes = value.strip().replace(".", ":").split(":")[:2]
        return time(int(hours), int(minutes))
    except (ValueError, TypeError):
        return None


def _day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def expand(extraction: ScheduleExtraction, today: date) -> list[Occurrence]:
    """Concrete, sorted, de-duplicated occurrences from today on, capped at MAX_EVENTS."""
    horizon_default = today + timedelta(weeks=DEFAULT_WEEKS)
    horizon_max = today + timedelta(weeks=MAX_WEEKS)
    found: dict[str, Occurrence] = {}

    for item in extraction.items:
        title = (item.title or "").strip()[:255]
        start_clock = _clock(item.start)
        if not title or start_clock is None:
            continue
        end_clock = _clock(item.end)
        details = " · ".join(part.strip() for part in (item.location, item.note) if part and part.strip()) or None

        days: list[date] = []
        one_off = _day(item.date)
        if one_off is not None:
            if today <= one_off <= horizon_max:
                days.append(one_off)
        elif item.weekday and 1 <= item.weekday <= 7:
            step = max(item.every_weeks or 1, 1)
            until = min(_day(item.until) or horizon_default, horizon_max)
            first = _day(item.first_date)
            cursor = first if first and first.isoweekday() == item.weekday else None
            if cursor is None:
                base = max(today, first or today)
                cursor = base + timedelta(days=(item.weekday - base.isoweekday()) % 7)
            while cursor < today:
                cursor += timedelta(weeks=step)
            while cursor <= until:
                days.append(cursor)
                cursor += timedelta(weeks=step)

        for day in days:
            start = datetime.combine(day, start_clock, tzinfo=TIMEZONE)
            end = datetime.combine(day, end_clock, tzinfo=TIMEZONE) if end_clock else start + timedelta(minutes=90)
            if end <= start:
                end = start + timedelta(minutes=90)
            occurrence = Occurrence(title=title, start=start, end=end, description=details)
            found.setdefault(occurrence.key, occurrence)

    return sorted(found.values(), key=lambda o: (o.start, o.title))[:MAX_EVENTS]


async def read_pdf(pdf: bytes, today: date | None = None) -> tuple[str | None, list[Occurrence]]:
    if not pdf.startswith(b"%PDF"):
        raise TaskExtractionError("Це не схоже на PDF.")
    if len(pdf) > MAX_PDF_BYTES:
        raise TaskExtractionError("PDF завеликий: до 10 МБ.")
    today = today or datetime.now(TIMEZONE).date()
    parts = [types.Part.from_bytes(data=pdf, mime_type="application/pdf"), "Витягни всі заняття з цього розкладу."]
    now = datetime.now(TIMEZONE)
    try:
        response = await _generate(parts, now, ScheduleExtraction, system=build_schedule_prompt(today))
    except Exception as exc:
        logger.error("Gemini could not read the timetable: %s", _safe_error(exc))
        raise TaskExtractionError(_failure_message(exc)) from exc
    extraction = _coerce(response)
    return extraction.title, expand(extraction, today)


def _coerce(response: object) -> ScheduleExtraction:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, ScheduleExtraction):
        return parsed
    if isinstance(parsed, dict):
        return ScheduleExtraction.model_validate(parsed)
    raw = (getattr(response, "text", None) or "").strip().strip("`")
    if raw.lower().startswith("json"):
        raw = raw[4:]
    try:
        return ScheduleExtraction.model_validate_json(raw.strip() or "{}")
    except Exception as exc:
        raise TaskExtractionError("Не вдалося прочитати розклад у файлі.") from exc


async def import_occurrences(
    session: AsyncSession,
    user_id: int,
    occurrences: list[Occurrence],
    *,
    assignee: Assignee,
    category: str | None,
    remind_before_minutes: int | None,
) -> tuple[list[Task], int]:
    """Create the tasks (skipping ones already there). Google sync is left to the caller."""
    from app.services import tasks as tasks_service

    created: list[Task] = []
    skipped = 0
    for occurrence in occurrences:
        duplicate = await session.scalar(
            select(Task.id).where(
                and_(
                    Task.title == occurrence.title,
                    Task.start_time == occurrence.start,
                    tasks_service._visible_to(user_id, await tasks_service._partner_of(session, user_id)),
                )
            )
        )
        if duplicate is not None:
            skipped += 1
            continue
        task = await tasks_service.create_task(
            session,
            user_id,
            TaskCreate(
                title=occurrence.title,
                description=occurrence.description,
                category=category,
                start_time=occurrence.start,
                end_time=occurrence.end,
                deadline=occurrence.end,
                remind_before_minutes=remind_before_minutes,
                assignee=assignee,
            ),
            push_google=False,
            notify=False,
        )
        created.append(task)
    return created, skipped


async def mirror_to_google(task_ids: list[int]) -> None:
    """Background: push imported tasks to Google one by one, on a fresh session."""
    from app.db import session_factory
    from app.services import tasks as tasks_service

    async with session_factory() as session:
        for task_id in task_ids:
            task = await session.get(Task, task_id)
            if task is not None:
                await tasks_service._mirror_google(session, task)

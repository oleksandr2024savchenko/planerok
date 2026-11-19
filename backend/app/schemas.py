from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.config import TIMEZONE
from app.models import Priority
from app.services.reminders import MAX_OFFSET_MINUTES


def _to_vienna(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE)


class Assignee(StrEnum):
    ME = "me"
    PARTNER = "partner"
    SHARED = "shared"


class TaskScope(StrEnum):
    TODAY = "today"
    UPCOMING = "upcoming"
    ALL = "all"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=64)
    priority: Priority = Priority.MEDIUM
    deadline: datetime | None = None
    remind_at: datetime | None = None
    remind_before_minutes: int | None = Field(default=None, ge=0, le=MAX_OFFSET_MINUTES)
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_shared: bool = False
    for_partner: bool = False
    # Who the task is for, seen from the author: me, the partner, or both. Wins over the two flags above.
    assignee: Assignee | None = None

    @field_validator("deadline", "remind_at", "start_time", "end_time")
    @classmethod
    def _localize(cls, value: datetime | None) -> datetime | None:
        return _to_vienna(value)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=64)
    priority: Priority | None = None
    deadline: datetime | None = None
    remind_at: datetime | None = None
    remind_before_minutes: int | None = Field(default=None, ge=0, le=MAX_OFFSET_MINUTES)
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_completed: bool | None = None
    is_shared: bool | None = None
    # Hand the task over, seen from whoever edits it: me, the partner, or both.
    assignee: Assignee | None = None

    @field_validator("title", "priority", "is_completed", "is_shared")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value

    @field_validator("deadline", "remind_at", "start_time", "end_time")
    @classmethod
    def _localize(cls, value: datetime | None) -> datetime | None:
        return _to_vienna(value)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    category: str | None
    priority: Priority
    deadline: datetime | None
    remind_at: datetime | None
    remind_before_minutes: int | None = None
    start_time: datetime | None
    end_time: datetime | None
    google_event_id: str | None
    sync_token: str | None
    is_completed: bool
    is_shared: bool = False
    owner_id: int | None = None
    assigned_to_id: int | None = None
    created_by_id: int | None = None
    focused_seconds: int = 0
    created_at: datetime
    read_only: bool = False
    all_day: bool = False
    source_name: str | None = None

    @field_serializer("deadline", "remind_at", "start_time", "end_time", "created_at")
    def _serialize_dt(self, value: datetime | None) -> str | None:
        localized = _to_vienna(value)
        return localized.isoformat() if localized else None


class FeedCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    name: str | None = Field(default=None, max_length=120)


class FeedRead(BaseModel):
    id: int
    name: str
    host: str
    last_sync_at: datetime | None = None
    last_error: str | None = None
    event_count: int = 0

    @field_serializer("last_sync_at")
    def _serialize_last_sync(self, value: datetime | None) -> str | None:
        localized = _to_vienna(value)
        return localized.isoformat() if localized else None


class CalendarStatusRead(BaseModel):
    connected: bool
    live: bool
    last_sync_at: datetime | None = None

    @field_serializer("last_sync_at")
    def _serialize_last_sync(self, value: datetime | None) -> str | None:
        localized = _to_vienna(value)
        return localized.isoformat() if localized else None


class TimerStart(BaseModel):
    task_id: int
    minutes: int = Field(ge=1, le=8 * 60)
    kind: Literal["focus", "break"] = "focus"


class TimerRead(BaseModel):
    """The live timer, with the server's own clock so the Mini App can count down without drift."""

    id: int
    task_id: int
    task_title: str
    kind: str
    status: str
    duration_seconds: int
    remaining_seconds: int
    task_focused_seconds: int
    server_now: datetime

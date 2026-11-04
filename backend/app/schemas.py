from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.config import TIMEZONE
from app.models import Priority


def _to_vienna(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE)


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
    start_time: datetime | None = None
    end_time: datetime | None = None

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
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_completed: bool | None = None

    @field_validator("title", "priority", "is_completed")
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
    start_time: datetime | None
    end_time: datetime | None
    google_event_id: str | None
    sync_token: str | None
    is_completed: bool
    created_at: datetime

    @field_serializer("deadline", "remind_at", "start_time", "end_time", "created_at")
    def _serialize_dt(self, value: datetime | None) -> str | None:
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

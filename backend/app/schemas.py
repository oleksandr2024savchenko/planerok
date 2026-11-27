from datetime import datetime, time
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
)

from app.config import TIMEZONE
from app.models import Priority, SpaceKind, SpaceRole, TaskStatus
from app.services.recurrence import InvalidRuleError, describe, normalize_rule


def _to_vienna(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE)


def _validate_rule(value: str | None) -> str | None:
    try:
        return normalize_rule(value)
    except InvalidRuleError as exc:
        raise ValueError(f"Unsupported recurrence rule: {exc}") from exc


class TaskScope(StrEnum):
    TODAY = "today"
    UPCOMING = "upcoming"
    ALL = "all"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    # Defaults to the author's personal space.
    space_id: int | None = None
    description: str | None = None
    category: str | None = Field(default=None, max_length=64)
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    # RRULE subset (FREQ=DAILY, FREQ=WEEKLY;BYDAY=MO, FREQ=MONTHLY;BYMONTHDAY=5, ...).
    recurrence: str | None = Field(default=None, max_length=128)
    deadline: datetime | None = None
    remind_at: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    @field_validator("deadline", "remind_at", "start_time", "end_time")
    @classmethod
    def _localize(cls, value: datetime | None) -> datetime | None:
        return _to_vienna(value)

    @field_validator("recurrence")
    @classmethod
    def _rule(cls, value: str | None) -> str | None:
        return _validate_rule(value)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=64)
    priority: Priority | None = None
    status: TaskStatus | None = None
    # Moves the task; requires write access to the target space.
    space_id: int | None = None
    # null stops the series.
    recurrence: str | None = Field(default=None, max_length=128)
    deadline: datetime | None = None
    remind_at: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_completed: bool | None = None

    @field_validator("title", "priority", "status", "space_id", "is_completed")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value

    @field_validator("deadline", "remind_at", "start_time", "end_time")
    @classmethod
    def _localize(cls, value: datetime | None) -> datetime | None:
        return _to_vienna(value)

    @field_validator("recurrence")
    @classmethod
    def _rule(cls, value: str | None) -> str | None:
        return _validate_rule(value)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    created_by_id: int
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
    status: TaskStatus
    is_completed: bool
    created_at: datetime
    updated_at: datetime
    recurrence_rule: str | None = None
    streak_current: int | None = None
    streak_best: int | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recurrence_label(self) -> str | None:
        return describe(self.recurrence_rule) if self.recurrence_rule else None

    @field_serializer("deadline", "remind_at", "start_time", "end_time", "created_at", "updated_at")
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


class SpaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None
    icon: str | None
    kind: SpaceKind
    role: SpaceRole


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=32)


class SpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=32)


class MeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    locale: str
    theme: str
    accent_color: str | None
    base_currency: str
    timezone: str


class NotificationPrefsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    digest_enabled: bool
    digest_time: time

    @field_serializer("digest_time")
    def _serialize_time(self, value: time) -> str:
        return value.strftime("%H:%M")


class NotificationPrefsUpdate(BaseModel):
    digest_enabled: bool | None = None
    digest_time: time | None = None

    @field_validator("digest_enabled", "digest_time")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value

    @field_validator("digest_time")
    @classmethod
    def _whole_minutes(cls, value: time) -> time:
        return value.replace(second=0, microsecond=0, tzinfo=None)

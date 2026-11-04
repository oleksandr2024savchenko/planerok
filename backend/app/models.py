from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, String, Text, false, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="task_priority", values_callable=lambda enum: [m.value for m in enum]),
        default=Priority.MEDIUM,
        server_default=Priority.MEDIUM.value,
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    google_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Cursor of the Google sync that last wrote this row. The calendar-level token lives on GoogleCalendarState.
    sync_token: Mapped[str | None] = mapped_column(Text)
    is_completed: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, title={self.title!r})"


class GoogleCalendarState(Base):
    """Single-row cursor for incremental sync and the events.watch channel."""

    __tablename__ = "google_calendar_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    calendar_id: Mapped[str] = mapped_column(String(255), default="primary")
    sync_token: Mapped[str | None] = mapped_column(Text)
    channel_id: Mapped[str | None] = mapped_column(String(128))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    channel_token: Mapped[str | None] = mapped_column(String(255))
    channel_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_token: Mapped[str | None] = mapped_column(Text)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

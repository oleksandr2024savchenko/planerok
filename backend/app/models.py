from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String, Text, Time, UniqueConstraint, false, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    partner_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    google_calendar_id: Mapped[str | None] = mapped_column(String(255))
    morning_time: Mapped[time] = mapped_column(Time, default=time(8, 0), server_default="08:00:00")
    afternoon_time: Mapped[time] = mapped_column(Time, default=time(14, 0), server_default="14:00:00")
    evening_time: Mapped[time] = mapped_column(Time, default=time(20, 0), server_default="20:00:00")
    theme_accent: Mapped[str] = mapped_column(String(32), default="violet", server_default="violet")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    assigned_to_id: Mapped[int | None] = mapped_column(BigInteger)
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
    partner_google_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Cursor of the Google sync that last wrote this row. The calendar-level token lives on GoogleCalendarState.
    sync_token: Mapped[str | None] = mapped_column(Text)
    is_completed: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, title={self.title!r})"


class ExternalCalendar(Base):
    """ICS feed subscribed by one of the two accounts."""

    __tablename__ = "external_calendars"
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_external_calendars_user_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(Text)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExternalEvent(Base):
    __tablename__ = "external_events"
    __table_args__ = (UniqueConstraint("calendar_id", "uid", name="uq_external_events_calendar_uid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("external_calendars.id", ondelete="CASCADE"), index=True)
    uid: Mapped[str] = mapped_column(String(700))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Local to Planer. The feed is replaced on every sync, so this flag is copied forward by occurrence uid.
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


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

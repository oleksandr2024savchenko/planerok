from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, false, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda enum: [m.value for m in enum])


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthProvider(StrEnum):
    TELEGRAM = "telegram"
    EMAIL = "email"


class SpaceKind(StrEnum):
    PERSONAL = "personal"
    SHARED = "shared"


class SpaceRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class User(TimestampMixin, Base):
    """Internal identity. Telegram is only one of the ways to sign in (see AuthIdentity)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), default="", server_default="")
    locale: Mapped[str] = mapped_column(String(8), default="uk", server_default="uk")
    theme: Mapped[str] = mapped_column(String(16), default="dark", server_default="dark")
    accent_color: Mapped[str | None] = mapped_column(String(16))
    base_currency: Mapped[str] = mapped_column(String(3), default="EUR", server_default="EUR")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Vienna", server_default="Europe/Vienna")


class AuthIdentity(TimestampMixin, Base):
    __tablename__ = "auth_identities"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_auth_identities_provider_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[AuthProvider] = mapped_column(_enum(AuthProvider, "auth_provider"))
    # Telegram user id (also the private chat id) or an email address.
    external_id: Mapped[str] = mapped_column(String(255))


class Space(TimestampMixin, Base):
    __tablename__ = "spaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(16))
    icon: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[SpaceKind] = mapped_column(_enum(SpaceKind, "space_kind"), default=SpaceKind.PERSONAL)


class SpaceMember(Base):
    """Every data access check goes through this table."""

    __tablename__ = "space_members"

    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[SpaceRole] = mapped_column(_enum(SpaceRole, "space_role"), default=SpaceRole.OWNER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    # Author of the task; reminders go to this user's Telegram chat.
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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

"""Users, sign-in identities and space membership."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuthIdentity,
    AuthProvider,
    Space,
    SpaceKind,
    SpaceMember,
    SpaceRole,
    User,
)

PERSONAL_SPACE_NAME = "Особисте"
WRITE_ROLES = frozenset({SpaceRole.OWNER, SpaceRole.EDITOR})


def _display_name(profile: Mapping[str, Any]) -> str:
    parts = [str(profile.get("first_name") or "").strip(), str(profile.get("last_name") or "").strip()]
    name = " ".join(part for part in parts if part) or str(profile.get("username") or "").strip()
    return name[:128]


async def get_or_create_telegram_user(
    session: AsyncSession,
    telegram_id: int,
    profile: Mapping[str, Any] | None = None,
) -> User:
    """Finds the user behind a Telegram account, creating it with a personal space on first sign-in."""
    external_id = str(telegram_id)
    user = await _user_by_identity(session, AuthProvider.TELEGRAM, external_id)
    if user is not None:
        return user

    user = User(display_name=_display_name(profile or {}))
    space = Space(name=PERSONAL_SPACE_NAME, kind=SpaceKind.PERSONAL)
    session.add_all([user, space])
    await session.flush()
    session.add_all(
        [
            AuthIdentity(user_id=user.id, provider=AuthProvider.TELEGRAM, external_id=external_id),
            SpaceMember(space_id=space.id, user_id=user.id, role=SpaceRole.OWNER),
        ]
    )
    try:
        await session.commit()
    except IntegrityError:
        # Two first requests raced; the other one created the user.
        await session.rollback()
        user = await _user_by_identity(session, AuthProvider.TELEGRAM, external_id)
        if user is None:
            raise
    return user


async def _user_by_identity(session: AsyncSession, provider: AuthProvider, external_id: str) -> User | None:
    return await session.scalar(
        select(User)
        .join(AuthIdentity, AuthIdentity.user_id == User.id)
        .where(AuthIdentity.provider == provider, AuthIdentity.external_id == external_id)
    )


def member_space_ids(user_id: int) -> Select[tuple[int]]:
    return select(SpaceMember.space_id).where(SpaceMember.user_id == user_id)


async def get_role(session: AsyncSession, user_id: int, space_id: int) -> SpaceRole | None:
    return await session.scalar(
        select(SpaceMember.role).where(SpaceMember.user_id == user_id, SpaceMember.space_id == space_id)
    )


async def can_write(session: AsyncSession, user_id: int, space_id: int) -> bool:
    return await get_role(session, user_id, space_id) in WRITE_ROLES


async def personal_space_id(session: AsyncSession, user_id: int) -> int:
    space_id = await session.scalar(
        select(Space.id)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(
            SpaceMember.user_id == user_id,
            SpaceMember.role == SpaceRole.OWNER,
            Space.kind == SpaceKind.PERSONAL,
            Space.deleted_at.is_(None),
        )
        .order_by(Space.id)
        .limit(1)
    )
    if space_id is None:
        raise LookupError(f"User {user_id} has no personal space")
    return space_id


async def list_spaces(session: AsyncSession, user_id: int) -> list[tuple[Space, SpaceRole]]:
    rows = await session.execute(
        select(Space, SpaceMember.role)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(SpaceMember.user_id == user_id, Space.deleted_at.is_(None))
        .order_by(Space.kind, Space.id)
    )
    return [(space, role) for space, role in rows.all()]


async def telegram_chat_id(session: AsyncSession, user_id: int) -> int | None:
    external_id = await session.scalar(
        select(AuthIdentity.external_id).where(
            AuthIdentity.user_id == user_id,
            AuthIdentity.provider == AuthProvider.TELEGRAM,
            AuthIdentity.deleted_at.is_(None),
        )
    )
    return int(external_id) if external_id else None

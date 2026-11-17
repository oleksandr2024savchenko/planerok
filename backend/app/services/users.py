"""Allowed couple accounts and their personal settings."""

from __future__ import annotations

import logging
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User

logger = logging.getLogger(__name__)

PINK_THEME = "pink"
VIOLET_THEME = "violet"


def _usable_calendar(calendar_id: str | None) -> str | None:
    value = (calendar_id or "").strip()
    if not value or value == "primary":
        return None
    return value


async def ensure_allowed_users(session: AsyncSession) -> list[User]:
    """Create or refresh the two accounts from ALLOWED_TELEGRAM_IDS."""
    settings = get_settings()
    ids = settings.allowed_telegram_id_list
    if not ids:
        logger.error("ALLOWED_TELEGRAM_IDS is empty; the bot and API will reject everyone")
        return []

    users: list[User] = []
    calendars = [_usable_calendar(settings.google_calendar_id), _usable_calendar(settings.google_partner_calendar_id)]
    for index, telegram_id in enumerate(ids):
        partner_id = ids[1 - index] if len(ids) == 2 else None
        theme = PINK_THEME if index == 1 else VIOLET_THEME
        calendar = calendars[index] if index < len(calendars) else None
        user = await session.get(User, telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                partner_telegram_id=partner_id,
                google_calendar_id=calendar,
                morning_time=time(8, 0),
                afternoon_time=time(14, 0),
                evening_time=time(20, 0),
                theme_accent=theme,
            )
            session.add(user)
        else:
            user.partner_telegram_id = partner_id
            if calendar and not user.google_calendar_id:
                user.google_calendar_id = calendar
            if index == 1 and user.theme_accent == VIOLET_THEME:
                user.theme_accent = theme
        users.append(user)
    await session.commit()
    return users


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.get(User, telegram_id)


async def partner_id(session: AsyncSession, telegram_id: int) -> int | None:
    user = await session.get(User, telegram_id)
    return user.partner_telegram_id if user else None


async def calendar_id_for(session: AsyncSession, telegram_id: int) -> str | None:
    user = await session.get(User, telegram_id)
    if user and user.google_calendar_id:
        return user.google_calendar_id
    settings = get_settings()
    if telegram_id == (settings.allowed_telegram_id_list[:1] or [None])[0]:
        if settings.google_calendar_id and settings.google_calendar_id != "primary":
            return settings.google_calendar_id
    return None


async def all_users(session: AsyncSession) -> list[User]:
    return list(await session.scalars(select(User)))

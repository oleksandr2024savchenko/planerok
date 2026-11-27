from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.telegram_auth import InitDataError, validate_init_data
from app.config import Settings, get_settings
from app.db import get_session
from app.models import User
from app.services import users as users_service

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    x_telegram_init_data: Annotated[str | None, Header()] = None,
) -> User:
    """Resolves the signed Telegram user to an internal user, creating it on first sign-in."""
    if x_telegram_init_data:
        try:
            profile = validate_init_data(
                x_telegram_init_data,
                bot_token=settings.bot_token,
                max_age_seconds=settings.init_data_ttl_seconds,
            )
        except InitDataError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid Telegram initData: {exc}") from exc
        return await users_service.get_or_create_telegram_user(session, int(profile["id"]), profile)

    if settings.dev_user_id is not None:
        # DEV_USER_ID is a Telegram user id, so local runs share data with the bot.
        return await users_service.get_or_create_telegram_user(session, settings.dev_user_id)

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Telegram-Init-Data header")


CurrentUserDep = Annotated[User, Depends(get_current_user)]

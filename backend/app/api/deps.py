from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.telegram_auth import InitDataError, validate_init_data
from app.config import Settings, get_settings
from app.db import get_session


async def get_current_user_id(
    settings: Annotated[Settings, Depends(get_settings)],
    x_telegram_init_data: Annotated[str | None, Header()] = None,
) -> int:
    if x_telegram_init_data:
        try:
            user = validate_init_data(
                x_telegram_init_data,
                bot_token=settings.bot_token,
                max_age_seconds=settings.init_data_ttl_seconds,
            )
        except InitDataError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid Telegram initData: {exc}") from exc
        return int(user["id"])

    if settings.dev_user_id is not None:
        return settings.dev_user_id

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Telegram-Init-Data header")


SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserIdDep = Annotated[int, Depends(get_current_user_id)]

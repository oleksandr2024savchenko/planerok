from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.api.deps import SessionDep, UserIdDep
from app.api.telegram_auth import InitDataError, validate_init_data
from app.config import get_settings
from app.models import User
from app.services.users import remember_name

router = APIRouter(tags=["me"])


class MeRead(BaseModel):
    telegram_id: int
    theme: str
    partner_telegram_id: int | None = None
    first_name: str | None = None
    partner_first_name: str | None = None


@router.get("/me", response_model=MeRead)
async def me(
    session: SessionDep,
    user_id: UserIdDep,
    x_telegram_init_data: Annotated[str | None, Header()] = None,
) -> MeRead:
    if x_telegram_init_data:
        settings = get_settings()
        try:
            tg_user = validate_init_data(
                x_telegram_init_data, bot_token=settings.bot_token, max_age_seconds=settings.init_data_ttl_seconds
            )
            await remember_name(session, user_id, tg_user.get("first_name"))
        except InitDataError:
            pass  # Already checked by UserIdDep; the name is optional.
    user = await session.get(User, user_id)
    partner = await session.get(User, user.partner_telegram_id) if user and user.partner_telegram_id else None
    return MeRead(
        telegram_id=user_id,
        theme=user.theme_accent if user else "violet",
        partner_telegram_id=user.partner_telegram_id if user else None,
        first_name=user.first_name if user else None,
        partner_first_name=partner.first_name if partner else None,
    )

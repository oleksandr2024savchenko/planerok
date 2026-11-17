from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SessionDep, UserIdDep
from app.models import User

router = APIRouter(tags=["me"])


class MeRead(BaseModel):
    telegram_id: int
    theme: str
    partner_telegram_id: int | None = None


@router.get("/me", response_model=MeRead)
async def me(session: SessionDep, user_id: UserIdDep) -> MeRead:
    user = await session.get(User, user_id)
    return MeRead(
        telegram_id=user_id,
        theme=user.theme_accent if user else "violet",
        partner_telegram_id=user.partner_telegram_id if user else None,
    )

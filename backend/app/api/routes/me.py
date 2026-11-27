from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.models import User
from app.schemas import MeRead, SpaceRead
from app.services import users as users_service

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeRead)
async def read_me(user: CurrentUserDep) -> User:
    return user


@router.get("/spaces", response_model=list[SpaceRead])
async def list_spaces(session: SessionDep, user: CurrentUserDep) -> list[SpaceRead]:
    return [
        SpaceRead(id=space.id, name=space.name, color=space.color, icon=space.icon, kind=space.kind, role=role)
        for space, role in await users_service.list_spaces(session, user.id)
    ]

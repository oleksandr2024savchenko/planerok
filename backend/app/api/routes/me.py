from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.models import NotificationPrefs, Space, SpaceKind, SpaceRole, User
from app.schemas import (
    MeRead,
    NotificationPrefsRead,
    NotificationPrefsUpdate,
    SpaceCreate,
    SpaceRead,
    SpaceUpdate,
)
from app.services import digest as digest_service
from app.services import users as users_service

router = APIRouter(tags=["me"])


def _space_read(space: Space, role: SpaceRole) -> SpaceRead:
    return SpaceRead(id=space.id, name=space.name, color=space.color, icon=space.icon, kind=space.kind, role=role)


async def _owned(session: SessionDep, user: User, space_id: int) -> Space:
    space = await users_service.owned_space(session, user.id, space_id)
    if space is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Space not found")
    return space


@router.get("/me", response_model=MeRead)
async def read_me(user: CurrentUserDep) -> User:
    return user


@router.get("/spaces", response_model=list[SpaceRead])
async def list_spaces(session: SessionDep, user: CurrentUserDep) -> list[SpaceRead]:
    return [_space_read(space, role) for space, role in await users_service.list_spaces(session, user.id)]


@router.post("/spaces", response_model=SpaceRead, status_code=status.HTTP_201_CREATED)
async def create_space(payload: SpaceCreate, session: SessionDep, user: CurrentUserDep) -> SpaceRead:
    try:
        space = await users_service.create_space(
            session, user.id, payload.name, color=payload.color, icon=payload.icon
        )
    except users_service.SpaceNameTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Space with this name already exists") from exc
    return _space_read(space, SpaceRole.OWNER)


@router.patch("/spaces/{space_id}", response_model=SpaceRead)
async def update_space(space_id: int, payload: SpaceUpdate, session: SessionDep, user: CurrentUserDep) -> SpaceRead:
    space = await _owned(session, user, space_id)
    try:
        space = await users_service.update_space(session, user.id, space, payload.model_dump(exclude_unset=True))
    except users_service.SpaceNameTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Space with this name already exists") from exc
    return _space_read(space, SpaceRole.OWNER)


@router.delete("/spaces/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(space_id: int, session: SessionDep, user: CurrentUserDep) -> Response:
    space = await _owned(session, user, space_id)
    if space.kind is SpaceKind.PERSONAL:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The personal space cannot be deleted")
    await users_service.delete_space(session, space)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/notifications", response_model=NotificationPrefsRead)
async def read_notifications(session: SessionDep, user: CurrentUserDep) -> NotificationPrefs:
    prefs = await digest_service.get_prefs(session, user.id)
    await session.commit()
    return prefs


@router.patch("/me/notifications", response_model=NotificationPrefsRead)
async def update_notifications(
    payload: NotificationPrefsUpdate, session: SessionDep, user: CurrentUserDep
) -> NotificationPrefs:
    prefs = await digest_service.get_prefs(session, user.id)
    changes = payload.model_dump(exclude_unset=True)
    if "digest_time" in changes and changes["digest_time"] != prefs.digest_time:
        # A new time today should still fire today.
        prefs.last_digest_on = None
    for field, value in changes.items():
        setattr(prefs, field, value)
    await session.commit()
    return prefs

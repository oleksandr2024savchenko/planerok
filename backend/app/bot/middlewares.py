from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings

_DENIED = "Цей планер лише для двох. Доступу немає."


class AllowlistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None and isinstance(event, Message):
            user = event.from_user
        if user is None and isinstance(event, CallbackQuery):
            user = event.from_user
        if user is None:
            return await handler(event, data)
        if get_settings().allows(user.id):
            return await handler(event, data)
        if isinstance(event, Message):
            await event.answer(_DENIED)
        elif isinstance(event, CallbackQuery):
            await event.answer(_DENIED, show_alert=True)
        return None


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)

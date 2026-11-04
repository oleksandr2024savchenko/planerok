import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from app.bot.handlers import get_root_router
from app.bot.middlewares import DbSessionMiddleware
from app.config import Settings
from app.db import session_factory

logger = logging.getLogger(__name__)


def create_bot(settings: Settings) -> Bot:
    return Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(settings: Settings) -> Dispatcher:
    storage: BaseStorage = RedisStorage.from_url(settings.redis_url) if settings.redis_url else MemoryStorage()
    dp = Dispatcher(storage=storage)
    middleware = DbSessionMiddleware(session_factory)
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)
    dp.include_router(get_root_router())
    return dp


async def configure_bot(bot: Bot, settings: Settings) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Відкрити планер"),
            BotCommand(command="help", description="Як додавати задачі"),
        ]
    )
    if settings.webapp_url.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Планер", web_app=WebAppInfo(url=settings.webapp_url))
        )
    else:
        logger.warning("WEBAPP_URL is not HTTPS; Telegram will refuse to open the Mini App")

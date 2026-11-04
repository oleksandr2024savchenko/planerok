import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.bot.setup import configure_bot, create_bot, create_dispatcher
from app.config import get_settings
from app.db import engine
from app.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("planer")


def _log_polling_exit(task: asyncio.Task[None]) -> None:
    if not task.cancelled() and (exc := task.exception()):
        logger.error("Bot polling crashed", exc_info=exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    bot = create_bot(settings)
    dp = create_dispatcher(settings)

    scheduler = setup_scheduler(bot, settings)
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=False)
    await configure_bot(bot, settings)
    polling = asyncio.create_task(
        dp.start_polling(bot, handle_signals=False, allowed_updates=dp.resolve_used_update_types())
    )
    polling.add_done_callback(_log_polling_exit)

    app.state.bot = bot
    from app.services.google_calendar import bootstrap_google

    google_bootstrap = asyncio.create_task(bootstrap_google())
    try:
        yield
    finally:
        google_bootstrap.cancel()
        with suppress(asyncio.CancelledError):
            await google_bootstrap
        with suppress(RuntimeError):
            await dp.stop_polling()
        # Crashes are already logged by the done-callback.
        with suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(polling, timeout=10)
        scheduler.shutdown(wait=False)
        await dp.storage.close()
        await bot.session.close()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Planer API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    # Polling and the scheduler live in-process, so run exactly one worker.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)

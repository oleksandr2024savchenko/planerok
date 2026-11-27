from aiogram import Router

from app.bot.handlers import digest, reminders, spaces, start, tasks


def get_root_router() -> Router:
    router = Router(name="root")
    # Order matters: the quick-task catch-all text handler must stay last.
    router.include_routers(start.router, spaces.router, digest.router, reminders.router, tasks.router)
    return router

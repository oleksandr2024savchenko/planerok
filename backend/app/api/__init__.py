from fastapi import APIRouter

from app.api.routes import feeds, google_calendar, me, tasks, timers

api_router = APIRouter()
# Before tasks: "/tasks/timer" must not be read as "/tasks/{task_id}".
api_router.include_router(timers.router)
api_router.include_router(tasks.router)
api_router.include_router(google_calendar.router)
api_router.include_router(feeds.router)
api_router.include_router(me.router)

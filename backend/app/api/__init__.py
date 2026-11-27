from fastapi import APIRouter

from app.api.routes import google_calendar, me, tasks

api_router = APIRouter()
api_router.include_router(me.router)
api_router.include_router(tasks.router)
api_router.include_router(google_calendar.router)

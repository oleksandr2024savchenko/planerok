import re
from datetime import datetime, time

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import digest as digest_service

router = Router(name="digest")

_TIME_RE = re.compile(r"^([01]?\d|2[0-3])[:.]([0-5]\d)$")
_OFF = {"off", "вимк", "вимкнути", "ні", "stop"}
_ON = {"on", "увімк", "увімкнути", "так", "start"}
_NOW = {"now", "зараз"}

USAGE = (
    "Команди:\n"
    "• <code>/digest 07:30</code> — змінити час\n"
    "• <code>/digest off</code> — вимкнути, <code>/digest on</code> — увімкнути\n"
    "• <code>/digest now</code> — показати дайджест зараз"
)


@router.message(Command("digest"))
async def cmd_digest(message: Message, command: CommandObject, session: AsyncSession, user: User, state: FSMContext) -> None:
    await state.clear()
    prefs = await digest_service.get_prefs(session, user.id)
    arg = (command.args or "").strip().lower()

    if arg in _NOW:
        zone = digest_service.user_zone(user)
        data = await digest_service.collect_digest(session, user, datetime.now(zone))
        await session.commit()
        await message.answer(digest_service.render_digest(data, zone) or "✨ На сьогодні задач немає.")
        return

    if arg in _OFF:
        prefs.digest_enabled = False
    elif arg in _ON:
        prefs.digest_enabled = True
    elif match := _TIME_RE.match(arg):
        new_time = time(int(match.group(1)), int(match.group(2)))
        if new_time != prefs.digest_time:
            prefs.last_digest_on = None
        prefs.digest_time = new_time
        prefs.digest_enabled = True
    elif arg:
        await session.commit()
        await message.answer(f"Не зрозумів. {USAGE}")
        return
    await session.commit()

    status = (
        f"☀️ Ранковий дайджест щодня о <b>{prefs.digest_time:%H:%M}</b>."
        if prefs.digest_enabled
        else "🔕 Ранковий дайджест вимкнено."
    )
    await message.answer(f"{status}\n\n{USAGE}")

"""PDF timetable sent to the bot → preview → «Мені / Партнеру / Разом»."""

import io
import logging
from datetime import datetime
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app import scheduler
from app.bot.callbacks import ImportCallback
from app.bot.states import ScheduleImportState
from app.config import TIMEZONE
from app.models import User
from app.schemas import Assignee
from app.services import schedule_import
from app.services.ai_agent import TaskExtractionError

logger = logging.getLogger(__name__)
router = Router(name="schedule")

_WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "нд")


def _events(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return f"{count} подію"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return f"{count} події"
    return f"{count} подій"


def _preview(title: str | None, occurrences: list[schedule_import.Occurrence]) -> str:
    lines = [f"📄 <b>{escape(title or 'Розклад')}</b>: знайшов {_events(len(occurrences))}."]
    for item in occurrences[:12]:
        when = item.start.astimezone(TIMEZONE)
        lines.append(f"• {_WEEKDAYS[when.weekday()]} {when:%d.%m %H:%M} — {escape(item.title)}")
    if len(occurrences) > 12:
        lines.append(f"… і ще {len(occurrences) - 12}")
    lines.append("\nКому додати? Нагадаю за 15 хв до кожної.")
    return "\n".join(lines)


async def _partner_name(session: AsyncSession, user_id: int) -> str:
    me = await session.get(User, user_id)
    partner = await session.get(User, me.partner_telegram_id) if me and me.partner_telegram_id else None
    return (partner.first_name if partner and partner.first_name else None) or "Партнеру"


@router.message(F.document & (F.document.mime_type == "application/pdf"))
async def on_pdf(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if message.from_user is None or message.document is None:
        return
    if (message.document.file_size or 0) > schedule_import.MAX_PDF_BYTES:
        await message.reply("📄 PDF завеликий: до 10 МБ.")
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    status = await message.reply("📄 Читаю розклад…")
    try:
        buffer = io.BytesIO()
        await message.bot.download(message.document, destination=buffer)
        title, occurrences = await schedule_import.read_pdf(buffer.getvalue())
    except TaskExtractionError as exc:
        await status.edit_text(f"📄 {exc}")
        return
    except Exception:
        logger.exception("Timetable PDF failed for %s", message.from_user.id)
        await status.edit_text("📄 Не вдалося прочитати файл. Спробуй ще раз або інший PDF.")
        return
    if not occurrences:
        await status.edit_text("📄 Не знайшов у файлі занять із датою чи днем тижня та часом.")
        return

    await state.set_state(ScheduleImportState.choosing_assignee)
    await state.update_data(
        schedule_title=title or (message.document.file_name or "").removesuffix(".pdf"),
        schedule_events=[
            {"title": o.title, "start": o.start.isoformat(), "end": o.end.isoformat(), "description": o.description}
            for o in occurrences
        ],
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🙋 Мені", callback_data=ImportCallback(choice=Assignee.ME.value))
    builder.button(text=f"👤 {await _partner_name(session, message.from_user.id)}", callback_data=ImportCallback(choice=Assignee.PARTNER.value))
    builder.button(text="⚡️ Разом", callback_data=ImportCallback(choice=Assignee.SHARED.value))
    builder.button(text="Скасувати", callback_data=ImportCallback(choice="cancel"))
    builder.adjust(3, 1)
    await status.edit_text(_preview(title, occurrences), reply_markup=builder.as_markup())


@router.callback_query(ImportCallback.filter())
async def on_import_choice(
    callback: CallbackQuery, callback_data: ImportCallback, session: AsyncSession, state: FSMContext
) -> None:
    message = callback.message if isinstance(callback.message, Message) else None
    data = await state.get_data()
    events = data.get("schedule_events") or []
    title = data.get("schedule_title")
    await state.clear()

    if callback_data.choice == "cancel" or not events:
        if message is not None:
            await message.edit_text("📄 Імпорт скасовано." if events else "📄 Цей розклад уже оброблено.", reply_markup=None)
        await callback.answer()
        return

    assignee = Assignee(callback_data.choice)
    await callback.answer("Додаю…")
    if message is not None:
        await message.edit_reply_markup(reply_markup=None)
    occurrences = [
        schedule_import.Occurrence(
            title=e["title"],
            start=datetime.fromisoformat(e["start"]),
            end=datetime.fromisoformat(e["end"]),
            description=e.get("description"),
        )
        for e in events
    ]
    created, skipped = await schedule_import.import_occurrences(
        session,
        callback.from_user.id,
        occurrences,
        assignee=assignee,
        category="навчання",
        remind_before_minutes=15,
    )
    who = {Assignee.ME: "тобі", Assignee.PARTNER: "партнеру", Assignee.SHARED: "вам обом"}[assignee]
    text = f"✅ Додав {_events(len(created))} {who}."
    if skipped:
        text += f" {skipped} вже були в планері — пропустив."
    if message is not None:
        await message.edit_text(text)
    if assignee is not Assignee.ME:
        await scheduler.notify_import(callback.from_user.id, len(created), title, shared=assignee is Assignee.SHARED)
    await schedule_import.mirror_to_google([task.id for task in created])

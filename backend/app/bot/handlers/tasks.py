import io
import logging
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import TaskAction, TaskActionCallback
from app.bot.keyboards import created_tasks_keyboard
from app.bot.parser import EmptyTitleError, parse_task
from app.bot.states import TaskEdit
from app.bot.texts import ASK_NEW_TIME_TEXT, created_list_text, format_dt, task_details
from app.config import get_settings
from app.models import Task
from app.schemas import TaskUpdate
from app.services import tasks as tasks_service
from app.services.ai_agent import (
    CATEGORY_SLUGS,
    ParsedTask,
    TaskExtractionError,
    TaskExtractionResult,
    finalize_task,
    parse_input_to_tasks,
    to_task_create,
)

logger = logging.getLogger(__name__)

router = Router(name="tasks")

_CATEGORY_FROM_SLUG = {slug: key for key, slug in CATEGORY_SLUGS.items()}
_CATEGORY_FROM_SLUG.update({key: key for key in CATEGORY_SLUGS})


def _regex_fallback(text: str) -> TaskExtractionResult:
    parsed = parse_task(text)
    category = _CATEGORY_FROM_SLUG.get((parsed.category or "").lower(), "personal")
    task = ParsedTask(
        title=parsed.title,
        description=parsed.description,
        category=category,  # type: ignore[arg-type]
        priority=parsed.priority.value,  # type: ignore[arg-type]
        deadline=parsed.deadline,
        remind_at=parsed.remind_at,
    )
    return TaskExtractionResult(tasks=[finalize_task(task)])


async def _extract(text: str | None = None, audio_bytes: bytes | None = None) -> TaskExtractionResult:
    try:
        result = await parse_input_to_tasks(text=text, audio_bytes=audio_bytes)
    except TaskExtractionError:
        if text:
            logger.warning("Gemini failed, falling back to heuristic parser")
            return _regex_fallback(text)
        raise
    if not result.tasks and text:
        try:
            return _regex_fallback(text)
        except EmptyTitleError:
            return result
    return result


async def _persist_tasks(
    session: AsyncSession,
    user_id: int,
    extraction: TaskExtractionResult,
) -> list[Task]:
    created: list[Task] = []
    for parsed in extraction.tasks:
        created.append(await tasks_service.create_task(session, user_id, to_task_create(parsed)))
    return created


async def _reply_with_tasks(message: Message, tasks: list[Task], status: Message | None = None) -> None:
    text = created_list_text(tasks)
    markup = created_tasks_keyboard([task.id for task in tasks], get_settings().webapp_url)
    if status is not None:
        await status.edit_text(text, reply_markup=markup)
        return
    await message.reply(text, reply_markup=markup)


@router.callback_query(TaskActionCallback.filter(F.action == TaskAction.EDIT_TIME))
async def on_edit_time(
    callback: CallbackQuery,
    callback_data: TaskActionCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    task = await tasks_service.get_task(session, callback.from_user.id, callback_data.task_id)
    if task is None:
        await callback.answer("Задачу не знайдено — можливо, її вже видалено.", show_alert=True)
        return
    await state.set_state(TaskEdit.waiting_for_time)
    await state.update_data(task_id=task.id)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(ASK_NEW_TIME_TEXT)


@router.callback_query(TaskActionCallback.filter(F.action == TaskAction.DELETE))
async def on_delete_task(
    callback: CallbackQuery,
    callback_data: TaskActionCallback,
    session: AsyncSession,
) -> None:
    task = await tasks_service.get_task(session, callback.from_user.id, callback_data.task_id)
    if task is None:
        await callback.answer("Задачу вже видалено.", show_alert=True)
        return
    title = task.title
    await tasks_service.delete_task(session, task)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"🗑 Видалено: <b>{escape(title)}</b>", reply_markup=None)
    await callback.answer("Видалено")


@router.message(TaskEdit.waiting_for_time, F.text)
async def on_new_reminder_time(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return
    data = await state.get_data()
    task_id = data.get("task_id")
    if not isinstance(task_id, int):
        await state.clear()
        return
    task = await tasks_service.get_task(session, message.from_user.id, task_id)
    if task is None:
        await state.clear()
        await message.reply("Задачу не знайдено — можливо, її вже видалено.")
        return

    try:
        extraction = await _extract(text=f"Перенеси нагадування задачі «{task.title}» на {message.text}")
    except (TaskExtractionError, EmptyTitleError):
        await message.reply("Не зрозумів час. Спробуй так: <code>завтра о 10:00</code>")
        return

    parsed = extraction.tasks[0] if extraction.tasks else None
    new_time = (parsed.remind_at or parsed.deadline) if parsed else None
    if parsed is None or new_time is None:
        await message.reply("Не бачу часу. Напиши, наприклад: <code>через 2 години</code>")
        return

    task = await tasks_service.update_task(
        session,
        task,
        TaskUpdate(remind_at=new_time, deadline=parsed.deadline or task.deadline),
    )
    await state.clear()
    when = format_dt(task.remind_at) if task.remind_at else "—"
    await message.reply(
        f"✏️ Нагадування оновлено: {when}\n\n{task_details(task)}",
        reply_markup=created_tasks_keyboard([task.id], get_settings().webapp_url),
    )


@router.message(F.voice)
async def on_voice_task(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.voice is None:
        return

    status: Message | None = None
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        status = await message.reply("🎙 Розпізнаю голосове...")

        buffer = io.BytesIO()
        await message.bot.download(message.voice, destination=buffer)
        audio_bytes = buffer.getvalue()
        logger.info(
            "Voice message from %s: %s bytes, duration=%ss",
            message.from_user.id,
            len(audio_bytes),
            message.voice.duration,
        )
        if not audio_bytes:
            logger.error("Telegram returned an empty voice file for message %s", message.message_id)
            await status.edit_text("🎙 Не вдалося завантажити голосове. Надішли його ще раз.")
            return

        try:
            extraction = await _extract(audio_bytes=audio_bytes)
        except TaskExtractionError as exc:
            logger.exception("Voice recognition failed for user %s", message.from_user.id)
            await status.edit_text(f"🎙 {exc}")
            return

        if not extraction.tasks:
            logger.info("Voice from %s contained no tasks", message.from_user.id)
            await status.edit_text("🤔 Не почув жодного завдання. Спробуй ще раз, трохи конкретніше.")
            return

        created = await _persist_tasks(session, message.from_user.id, extraction)
        await _reply_with_tasks(message, created, status=status)
    except Exception:
        logger.exception(
            "Voice handler crashed for user %s message %s",
            message.from_user.id,
            message.message_id,
        )
        if status is not None:
            await status.edit_text("🎙 Не вдалося розпізнати повідомлення")
        else:
            await message.reply("🎙 Не вдалося розпізнати повідомлення")


@router.message(F.text & ~F.text.startswith("/"))
async def quick_create_task(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.text is None:
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    status = await message.reply("🧠 Розпізнаю задачу...")

    try:
        extraction = await _extract(text=message.text)
    except (TaskExtractionError, EmptyTitleError):
        await status.edit_text(
            "🤔 Не бачу назви задачі. Напиши, наприклад: <code>завтра на 10 ранку зал</code>"
        )
        return

    if not extraction.tasks:
        await status.edit_text("🤔 Не вдалося витягти завдання. Сформулюй конкретніше.")
        return

    created = await _persist_tasks(session, message.from_user.id, extraction)
    await _reply_with_tasks(message, created, status=status)

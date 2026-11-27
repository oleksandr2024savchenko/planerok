from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SpaceKind, SpaceRole, User
from app.services import users as users_service

router = Router(name="spaces")

_ROLE_LABELS = {SpaceRole.OWNER: "власник", SpaceRole.EDITOR: "редактор", SpaceRole.VIEWER: "перегляд"}


@router.message(Command("spaces"))
async def cmd_spaces(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    await state.clear()
    lines = ["📂 <b>Твої простори</b>"]
    for space, role in await users_service.list_spaces(session, user.id):
        default = " · за замовчуванням" if space.kind is SpaceKind.PERSONAL else ""
        tag = "#" + space.name.replace(" ", "")
        lines.append(f"• <b>{escape(space.name)}</b> <code>{escape(tag)}</code> — {_ROLE_LABELS[role]}{default}")
    lines.append(
        "\nДодай <code>#Назва</code> до задачі, щоб покласти її в простір.\n"
        "Новий простір: <code>/newspace Бізнес</code>"
    )
    await message.answer("\n".join(lines))


@router.message(Command("newspace"))
async def cmd_new_space(
    message: Message, command: CommandObject, session: AsyncSession, user: User, state: FSMContext
) -> None:
    await state.clear()
    name = (command.args or "").strip()
    if not name or len(name) > 64:
        await message.answer("Напиши назву після команди, наприклад: <code>/newspace Бізнес</code>")
        return
    try:
        space = await users_service.create_space(session, user.id, name)
    except users_service.SpaceNameTakenError:
        await message.answer(f"Простір «{escape(name)}» уже є.")
        return
    tag = "#" + space.name.replace(" ", "")
    await message.answer(
        f"✨ Простір <b>{escape(space.name)}</b> створено.\n"
        f"Пиши задачі з <code>{escape(tag)}</code>, наприклад: <code>Звіт {escape(tag)} !high @завтра</code>"
    )

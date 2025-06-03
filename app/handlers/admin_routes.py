# app/handlers/admin_routes.py
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message

import os
from app.database.models import (
    add_admin,
    is_admin,
    list_all_requests,
    block_master,
    unblock_master,
)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or ""

router = Router()


# ─────────────────── FSM ────────────────────
class AdminLogin(StatesGroup):
    waiting_password = State()


# ─────────────────── команды справки ────────
ADMIN_HELP = (
    "👑 <b>Режим администратора включён</b>\n\n"
    "Доступные команды:\n"
    "  • /all_requests [N] — последние N (по умолчанию 30) заявок\n"
    "  • /block_master [telegram_id] — заблокировать мастера\n"
    "  • /unblock_master [telegram_id] — разблокировать мастера\n"
    "  • /logout_admin — выйти из режима администратора"
)


# ─────────────────── /login_admin ───────────
@router.message(Command("login_admin"))
async def login_admin_cmd(message: Message, state: FSMContext):
    # уже админ — показываем help и выходим
    if await is_admin(message.from_user.id):
        return await message.answer(ADMIN_HELP, parse_mode="HTML")

    await state.set_state(AdminLogin.waiting_password)
    await message.answer(
        "🔑 Введите пароль администратора:",
        parse_mode=None
    )


# ─────────────────── приём пароля ───────────
@router.message(StateFilter(AdminLogin.waiting_password), F.text)
async def admin_password_entered(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await add_admin(message.from_user.id)
        await state.clear()
        await message.answer("✅ Пароль принят.\n\n" + ADMIN_HELP, parse_mode="HTML")
    else:
        await state.clear()
        await message.answer("🚫 Неверный пароль.", parse_mode=None)


# ─────────────────── /logout_admin ──────────
@router.message(Command("logout_admin"))
async def logout_admin(message: Message):
    # Реальной таблицы «active admins» нет, поэтому просто «забываем» об этом
    await message.answer("👋 Вы вышли из режима администратора.")


# ─────────────────── /all_requests [N] ──────
@router.message(Command("all_requests"))
async def cmd_all_requests(message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    limit = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 30

    rows = await list_all_requests(limit)
    if not rows:
        return await message.answer("Заявок нет.")

    txt = ["🗂 <b>Последние заявки</b>:"]
    for r in rows:
        txt.append(f"#{r[0]} • {r[1]} • {r[2]} • {r[3][:30]}… • {r[4][5:16]}")
    await message.answer("\n".join(txt), parse_mode="HTML")


# ─────────────────── /block_master <id> ─────
@router.message(Command("block_master"))
async def cmd_block_master(message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("Используйте:\n/block_master [telegram_id]")
    await block_master(int(parts[1]))
    await message.answer("🔒 Мастер заблокирован (is_active=0).")


# ─────────────────── /unblock_master <id> ───
@router.message(Command("unblock_master"))
async def cmd_unblock_master(message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("Используйте:\n/unblock_master [telegram_id]")
    await unblock_master(int(parts[1]))
    await message.answer("🔓 Мастер разблокирован (is_active=1).")

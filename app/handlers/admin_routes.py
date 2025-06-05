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
    get_request_by_id,
    force_close_request,
    list_recent_reviews,
)
from app.bots import user_bot, master_bot
from app.handlers.master import make_master_menu
import logging

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or ""

router = Router()


# ─────────────────── FSM ────────────────────
class AdminLogin(StatesGroup):
    waiting_password = State()


class BlockMasterFSM(StatesGroup):
    waiting_id = State()


class UnblockMasterFSM(StatesGroup):
    waiting_id = State()


# ─────────────────── команды справки ────────
ADMIN_HELP = (
    "👑 <b>Режим администратора включён</b>\n\n"
    "Доступные команды:\n"
    "  • /all_requests [N] — последние N (по умолчанию 30) заявок\n"
    "  • /block_master [telegram_id] — заблокировать мастера\n"
    "  • /unblock_master [telegram_id] — разблокировать мастера\n"
    "  • /close_request [id] — закрыть заявку принудительно\n"
    "  • /recent_reviews — последние 10 заявок с отзывами\n"
    "  • /logout_admin — выйти из режима администратора"
)


# ─────────────────── /login_admin ───────────
@router.message(Command("login_admin"))
async def login_admin_cmd(message: Message, state: FSMContext):
    # уже админ — показываем help и выходим
    if await is_admin(message.from_user.id):
        return await message.answer(
            ADMIN_HELP, parse_mode="HTML",
            reply_markup=make_master_menu(True),
        )

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
        await message.answer(
            "✅ Пароль принят.\n\n" + ADMIN_HELP,
            parse_mode="HTML",
            reply_markup=make_master_menu(True),
        )
    else:
        await state.clear()
        await message.answer("🚫 Неверный пароль.", parse_mode=None)


# ─────────────────── /logout_admin ──────────
@router.message(Command("logout_admin"))
async def logout_admin(message: Message):
    # Реальной таблицы «active admins» нет, поэтому просто «забываем» об этом
    await message.answer(
        "👋 Вы вышли из режима администратора.",
        reply_markup=make_master_menu(False),
    )


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
async def cmd_block_master(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].isdigit():
        await block_master(int(parts[1]))
        return await message.answer("🔒 Мастер заблокирован (is_active=0).")

    await state.set_state(BlockMasterFSM.waiting_id)
    await message.answer("Введите telegram_id мастера для блокировки:")


@router.message(StateFilter(BlockMasterFSM.waiting_id), F.text)
async def block_master_enter_id(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    if not message.text.isdigit():
        return await message.answer("Введите число.")
    await block_master(int(message.text))
    await state.clear()
    await message.answer("🔒 Мастер заблокирован (is_active=0).")


# ─────────────────── /unblock_master <id> ───
@router.message(Command("unblock_master"))
async def cmd_unblock_master(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].isdigit():
        await unblock_master(int(parts[1]))
        return await message.answer("🔓 Мастер разблокирован (is_active=1).")

    await state.set_state(UnblockMasterFSM.waiting_id)
    await message.answer("Введите telegram_id мастера для разблокировки:")


@router.message(StateFilter(UnblockMasterFSM.waiting_id), F.text)
async def unblock_master_enter_id(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    if not message.text.isdigit():
        return await message.answer("Введите число.")
    await unblock_master(int(message.text))
    await state.clear()
    await message.answer("🔓 Мастер разблокирован (is_active=1).")


# ─────────────────── /close_request <id> ───
@router.message(Command("close_request"))
async def cmd_close_request(message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("Используйте:\n/close_request [id]")
    req_id = int(parts[1])
    req = await get_request_by_id(req_id)
    if not req:
        return await message.answer("Заявка не найдена.")

    master_id = await force_close_request(req_id)
    user_id = req[1]

    try:
        await user_bot.send_message(
            user_id,
            f"ℹ️ Ваша заявка №{req_id} закрыта администратором.",
        )
    except Exception as e:
        logging.exception(f"Не смог уведомить клиента {user_id}: {e}")

    if master_id:
        try:
            await master_bot.send_message(
                master_id,
                f"⚠️ Заявка №{req_id} закрыта администратором. "
                "Оплатите комиссию командой /pay_commission",
            )
        except Exception as e:
            logging.exception(f"Не смог уведомить мастера {master_id}: {e}")

    await message.answer("✅ Заявка закрыта администратором.")


# ─────────────────── /recent_reviews ───────
@router.message(Command("recent_reviews"))
async def cmd_recent_reviews(message: Message):
    if not await is_admin(message.from_user.id):
        return
    rows = await list_recent_reviews(10)
    if not rows:
        return await message.answer("Отзывов пока нет.")

    lines = ["📝 <b>Последние отзывы</b>:"]
    for r in rows:
        req_id, rating, comment, master_name = r
        comment = comment or "-"
        lines.append(f"#{req_id} • {master_name} • {rating}★ • {comment[:40]}")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ────────────────── Кнопки меню ─────────────
@router.message(F.text == "🔒 Заблокировать мастера")
async def btn_block_master(message: Message, state: FSMContext):
    await cmd_block_master(message, state)


@router.message(F.text == "🔓 Разблокировать мастера")
async def btn_unblock_master(message: Message, state: FSMContext):
    await cmd_unblock_master(message, state)


@router.message(F.text == "📝 История заявок")
async def btn_recent_reviews(message: Message):
    await cmd_recent_reviews(message)

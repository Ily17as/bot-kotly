# app/handlers/client_confirm.py
from aiogram import Router
from aiogram.types import CallbackQuery
from app.database.models import get_request_by_id, complete_request
from app.bots import master_bot
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


def make_pay_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить комиссию", callback_data="pay")]
        ]
    )


@router.callback_query(lambda c: c.data and c.data.startswith("confirm:"))
async def cb_client_confirm(query: CallbackQuery):
    request_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    req = await get_request_by_id(request_id)
    if not req or req[1] != user_id or req[10] != "await_client":
        return await query.answer("⛔ Подтвердить нельзя.", show_alert=True)

    master_id = req[11]
    await complete_request(request_id, master_id)

    await query.message.edit_reply_markup()
    await query.message.answer("✅ Спасибо! Заявка закрыта.")
    await query.answer()

    try:
        await master_bot.send_message(
            master_id,
            f"🎉 Клиент подтвердил завершение заявки №{request_id}. "
            "Не забудьте оплатить комиссию 100 ₽ командой /pay_commission",
            parse_mode="HTML",
            reply_markup=make_pay_kb(),
        )
    except Exception as e:
        logging.exception(f"Не смог уведомить мастера {master_id}: {e}")

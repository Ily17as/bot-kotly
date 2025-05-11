from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.database.models import (
    add_master,
    list_available_masters,
    take_request,
    decline_request,
    complete_request,
    pay_commission,
)

router = Router()

# 3.1 Регистрация мастера
@router.message(Command("register_master"))
async def cmd_register_master(message: Message):
    user = message.from_user
    await add_master(user.id, user.username or "")
    await message.answer("✅ Вы зарегистрированы как мастер и готовы к новым заявкам!")

# 3.2 Inline-клавиатура для заявки
def make_request_kb(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 Взять в работу", callback_data=f"take:{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить",     callback_data=f"decline:{request_id}")
        ]
    ])

# 3.3 Колбэк «Взять в работу»
@router.callback_query(lambda c: c.data and c.data.startswith("take:"))
async def cb_take_request(query: CallbackQuery):
    _, req_id = query.data.split(":")
    master_id = query.from_user.id
    await take_request(int(req_id), master_id)
    # достаём полный адрес из БД, здесь упрощённо:
    # full_address = await get_request_address(req_id)
    full_address = " — тут будет адрес клиента"
    await query.bot.send_message(
        chat_id=master_id,
        text=f"✅ Заявка #{req_id} принята!\n📍 Адрес клиента: {full_address}"
    )
    await query.message.edit_reply_markup()  # убираем кнопки

# 3.4 Колбэк «Отклонить»
@router.callback_query(lambda c: c.data and c.data.startswith("decline:"))
async def cb_decline_request(query: CallbackQuery):
    _, req_id = query.data.split(":")
    master_id = query.from_user.id

    await decline_request(int(req_id), master_id)
    await query.answer("❌ Вы отклонили заявку, она вновь откроется для других мастеров.")

# 3.5 Колбэк «Выполнено» (будет добавлен следующими шагами)
@router.callback_query(lambda c: c.data and c.data.startswith("done:"))
async def cb_done_request(query: CallbackQuery):
    _, req_id = query.data.split(":")
    master_id = query.from_user.id

    await complete_request(int(req_id), master_id)
    await query.message.answer("🔔 Заявка завершена! Пожалуйста, оплатите комиссию.")
    await query.message.edit_reply_markup()  # убрать старые кнопки

# 3.6 Колбэк «Оплатить комиссию» (будет позже реализован платёж)
@router.callback_query(lambda c: c.data and c.data.startswith("pay:"))
async def cb_pay_commission(query: CallbackQuery):
    master_id = query.from_user.id
    await pay_commission(master_id)
    await query.message.answer("💳 Комиссия оплачена, вы можете брать новые заявки.")
    await query.message.edit_reply_markup()

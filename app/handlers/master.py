from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
from app.database.models import (
    add_master,
    list_available_masters,
    take_request,
    decline_request,
    complete_request,
    pay_commission,
    get_master_by_id,
    get_request_by_id, wait_client_confirmation,
)
from app.bots import user_bot
router = Router()


class MasterRegistration(StatesGroup):
    full_name = State()
    phone = State()


# — /start и /help
@router.message(Command("start"))
async def master_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в бот мастера!\n\n"
        "Команды:\n"
        "/register_master — зарегистрироваться и получать заявки\n"
        "/help — показать это сообщение"
    )


@router.message(Command("help"))
async def master_help(message: Message):
    await master_start(message)


# — начало диалога регистрации
@router.message(Command("register_master"))
async def cmd_register_master(message: Message, state: FSMContext):
    await state.set_state(MasterRegistration.full_name)
    await message.answer("👤 Пожалуйста, введите ваше полное имя:")


@router.message(StateFilter(MasterRegistration.full_name), F.text)
async def process_master_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await state.set_state(MasterRegistration.phone)
    await message.answer("📱 Теперь введите, пожалуйста, ваш номер телефона в формате +71234567890:")


@router.message(StateFilter(MasterRegistration.phone), F.text)
async def process_master_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    full_name = data["full_name"]
    phone = message.text.strip()
    user = message.from_user
    username = user.username or ""

    # сохраняем в БД
    await add_master(user.id, username, full_name, phone)

    await message.answer(
        "✅ Мастер зарегистрирован!\n\n"
        f"Ваши данные:\n"
        f"👤 Имя: {full_name}\n"
        f"📞 Телефон: {phone}\n\n"
        "Теперь вы будете получать новые заявки."
    )
    await state.clear()


# inline-клавиатура для новых заявок
def make_request_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔧 Взять в работу", callback_data=f"take:{request_id}"),
        InlineKeyboardButton(text="❌ Отклонить",     callback_data=f"decline:{request_id}")
    ]])

def make_done_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Завершить", callback_data=f"done:{request_id}"
                )
            ]
        ]
    )
def make_client_confirm_kb(request_id: int) -> InlineKeyboardMarkup:
    """
    Однокнопочная клавиатура, которую увидит клиент,
    когда мастер пометит заявку выполненной.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{request_id}")]
        ]
    )


# — «Взять в работу»
@router.callback_query(lambda c: c.data and c.data.startswith("take:"))
async def cb_take_request(query: CallbackQuery):
    request_id = int(query.data.split(":", 1)[1])
    master_id  = query.from_user.id

    # — проверяем мастера
    master = await get_master_by_id(master_id)
    # master[7] = is_active, master[5] = active_orders, master[6] = has_debt
    if not master or master[7] != 1:
        return await query.answer("⛔ Вы не зарегистрированы или заблокированы.", show_alert=True)
    if master[5] >= 2:
        return await query.answer("⛔ У вас уже 2 активные заявки.", show_alert=True)
    if master[6] == 1:
        return await query.answer("⛔ У вас есть неоплаченная комиссия. Оплатите её.", show_alert=True)

    # — проверяем заявку
    req = await get_request_by_id(request_id)
    # req[10] = status
    if not req or req[10] != "open":
        return await query.answer("⛔ Заявка недоступна.", show_alert=True)

    # — захватываем
    await take_request(request_id, master_id)

    # --- достаём то, что нужно отправить мастеру --------------------
    location_text = req[5]  # TEXT-адрес (col 5)
    latitude = req[6]  # REAL (col 6)  | может быть None
    longitude = req[7]  # REAL (col 7)  | может быть None

    # 1) подтверждающее сообщение
    await query.bot.send_message(
        master_id,
        (
            f"✅ Заявка #{request_id} принята в работу!\n"
            f"📍 Адрес клиента: {location_text}"
        ),
        parse_mode="HTML",
    )

    client_id = req[1]
    client_username = req[2]

    if not client_username or client_username == "":
        client_username = f"<a href='tg://user?id={client_id}'>Профиль в Telegram</a>"

    await query.bot.send_message(
        master_id,
        f"👤 Контакт заказчика: {client_username}"
        f"\nНе забудьте отметить выполненную работу по кнопке ниже",
        reply_markup=make_done_kb(request_id),
        parse_mode="HTML",
    )

    # 2) геопин – только теперь
    if latitude is not None and longitude is not None:
        await query.bot.send_location(
            master_id,
            latitude=latitude,
            longitude=longitude,
        )

    # убираем кнопки у сообщения-уведомления в чате мастеров
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logging.exception(f"Не удалось поставить кнопку 'Завершить' {request_id=}: {e}")


# — «Отклонить»
@router.callback_query(lambda c: c.data and c.data.startswith("decline:"))
async def cb_decline_request(query: CallbackQuery):
    request_id = int(query.data.split(":", 1)[1])
    master_id  = query.from_user.id

    master = await get_master_by_id(master_id)
    if not master or master[7] != 1:
        return await query.answer("⛔ Вы не зарегистрированы или заблокированы.", show_alert=True)

    req = await get_request_by_id(request_id)
    # req[7]=status, req[8]=master_id
    if not req or req[10] != "in_progress" or req[11] != master_id:
        return await query.answer("⛔ Нечего отклонять.", show_alert=True)

    await decline_request(request_id, master_id)
    await query.answer("❌ Вы отклонили заявку — она вновь открыта.", show_alert=True)


# — «Выполнено»
@router.callback_query(lambda c: c.data and c.data.startswith("done:"))
async def cb_done_request(query: CallbackQuery):
    request_id = int(query.data.split(":", 1)[1])
    master_id = query.from_user.id

    # — проверки такие же, как раньше —
    master = await get_master_by_id(master_id)
    if not master or master[7] != 1:
        return await query.answer("⛔ Вы не зарегистрированы или заблокированы.", show_alert=True)

    req = await get_request_by_id(request_id)
    if not req or req[10] != "in_progress" or req[11] != master_id:
        return await query.answer("⛔ Эта заявка не у вас в работе.", show_alert=True)

    # 1. переводим в await_client
    await wait_client_confirmation(request_id, master_id)

    # 2. сообщаем МАСТЕРУ
    await query.message.answer("⌛ Ожидаем подтверждения клиента.")
    await query.message.edit_reply_markup()          # убираем кнопку
    await query.answer("Запрос отправлен клиенту")

    # 3. сообщаем КЛИЕНТУ
    client_id = req[1]
    await user_bot.send_message(
        client_id,
        f"🔔 Мастер отметил, что работа по заявке №{request_id} выполнена.\n"
        "Если всё в порядке, подтвердите завершение:",
        reply_markup=make_client_confirm_kb(request_id),
        parse_mode="HTML",
    )


# — «Оплатить комиссию»
@router.message(Command("pay_commission"))
async def cmd_pay_commission(message: Message):
    master_id = message.from_user.id

    master = await get_master_by_id(master_id)
    if not master or master[7] != 1:          # is_active
        return await message.answer("⛔ Вы не зарегистрированы или заблокированы.")
    if master[6] == 0:                        # has_debt
        return await message.answer("ℹ️ У вас нет долга по комиссии.")

    await pay_commission(master_id)
    await message.answer("💳 Комиссия оплачена, вы снова в очереди на заявки.")

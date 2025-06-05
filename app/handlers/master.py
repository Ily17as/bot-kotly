from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import logging
from app.database.models import (
    add_master,
    list_available_masters,
    take_request,
    decline_request,
    complete_request,
    pay_commission,
    list_master_requests,
    get_master_by_id,
    get_request_by_id,
    list_admins,
    is_admin,
)
from app.bots import user_bot
from app.handlers.client_review import make_rating_kb
from aiogram.types import BufferedInputFile
from io import BytesIO
router = Router()

# Постоянное меню для мастера
MASTER_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📄 Мои заявки")],
        [KeyboardButton(text="💳 Оплатить комиссию")],
        [KeyboardButton(text="✅ Закрыть по номеру")],
    ],
    resize_keyboard=True,
)


def make_master_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    """Создаёт меню мастера, добавляя админские кнопки при необходимости."""
    keyboard = [
        [KeyboardButton(text="📄 Мои заявки")],
        [KeyboardButton(text="💳 Оплатить комиссию")],
        [KeyboardButton(text="✅ Закрыть по номеру")],
    ]
    if is_admin:
        keyboard.extend([
            [KeyboardButton(text="🔒 Заблокировать мастера")],
            [KeyboardButton(text="🔓 Разблокировать мастера")],
            [KeyboardButton(text="📝 История заявок")],
        ])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def make_master_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    """Создаёт меню мастера, добавляя админские кнопки при необходимости."""
    keyboard = [
        [KeyboardButton(text="📄 Мои заявки")],
        [KeyboardButton(text="💳 Оплатить комиссию")],
        [KeyboardButton(text="✅ Закрыть по номеру")],
    ]
    if is_admin:
        keyboard.extend([
            [KeyboardButton(text="🔒 Заблокировать мастера")],
            [KeyboardButton(text="🔓 Разблокировать мастера")],
            [KeyboardButton(text="📝 История заявок")],
        ])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def make_master_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    """Создаёт меню мастера, добавляя админские кнопки при необходимости."""
    keyboard = [
        [KeyboardButton(text="📄 Мои заявки")],
        [KeyboardButton(text="💳 Оплатить комиссию")],
        [KeyboardButton(text="✅ Закрыть по номеру")],
    ]
    if is_admin:
        keyboard.extend([
            [KeyboardButton(text="🔒 Заблокировать мастера")],
            [KeyboardButton(text="🔓 Разблокировать мастера")],
            [KeyboardButton(text="📝 История заявок")],
        ])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


class MasterRegistration(StatesGroup):
    full_name = State()
    phone = State()


class CloseRequestFSM(StatesGroup):
    request_id = State()


# — /start и /help
@router.message(Command("start"))
async def master_start(message: Message):
    admin = await is_admin(message.from_user.id)
    text = (
        "👋 Добро пожаловать в бот мастера!\n\n"
        "Команды:\n"
        "/register_master — зарегистрироваться и получать заявки\n"
        "/finish_request [id] — закрыть заявку по номеру\n"
        "/my_requests — мои активные заявки\n"
        "/help — показать это сообщение"
        reply_markup=MASTER_MENU,
    )
    if admin:
        text += (
            "\n\nАдминские команды:\n"
            "/all_requests [N] — последние N заявок\n"
            "/block_master [telegram_id] — заблокировать мастера\n"
            "/unblock_master [telegram_id] — разблокировать мастера\n"
            "/close_request [id] — закрыть заявку принудительно\n"
            "/recent_reviews — история 10 заявок с отзывами\n"
            "/logout_admin — выйти из режима администратора"
        )

    await message.answer(text, reply_markup=make_master_menu(admin))


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

    is_admin_user = await is_admin(user.id)
    await message.answer(
        "✅ Мастер зарегистрирован!\n\n"
        f"Ваши данные:\n"
        f"👤 Имя: {full_name}\n"
        f"📞 Телефон: {phone}\n\n"
        "Теперь вы будете получать новые заявки.\n"
        "Для закрытия заявки по номеру используйте /finish_request",
        reply_markup=make_master_menu(is_admin_user),
    )
    await state.clear()


# inline-клавиатура для новых заявок
def make_request_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔧 Взять в работу", callback_data=f"take:{request_id}")
    ]])

def make_done_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Завершить", callback_data=f"done:{request_id}"
                ),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline:{request_id}")
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


async def notify_others_later(delay: int, other_masters: list[int], request_id: int, bot):
    """
    Корутина ждёт `delay` секунд, а потом рассылает уведомление всем мастерам из other_masters.
    Если delay == 0, сразу идёт к рассылке.
    """
    if delay > 0:
        # заснуть на то количество секунд, которое осталось до 5 минут
        await asyncio.sleep(delay)

    # после пробуждения (или сразу, если delay=0) рассылаем сообщение
    for mid in other_masters:
        try:
            # Важно: в параметрах send_message нужно писать text=<строка>, а не text: <строка>
            await bot.send_message(
                mid,
                text=f"Заявка №{request_id} уже принята другим мастером."
            )
        except Exception as e:
            logging.exception(f"Не смог уведомить мастера {mid}: {e}")


async def resend_request_to_masters(request_id: int, bot, exclude: list[int] | None = None):
    """Отправляет открытую заявку всем мастерам заново."""
    req = await get_request_by_id(request_id)
    if not req or req[10] != "open":
        return

    masters = await list_available_masters()
    if exclude:
        masters = [m for m in masters if m not in exclude]

    description = req[3]
    settlement = req[4]
    media_id = req[8]
    media_type = req[9]

    msg_txt = (
        f"🆕 Заявка №{request_id}!\n"
        f"📍 Район: {settlement}\n"
        f"🧾 Проблема: {description}"
    )[:1024]

    buffer_bytes: bytes | None = None
    if media_id:
        try:
            file_info = await user_bot.get_file(media_id)
            file_obj = await user_bot.download_file(file_info.file_path)
            buffer_bytes = file_obj.getvalue() if isinstance(file_obj, BytesIO) else file_obj
        except Exception as e:
            logging.exception(f"Не смог скачать медиа по заявке {request_id}: {e}")

    uploaded_file_id: str | None = None
    for mid in masters:
        try:
            if buffer_bytes:
                if uploaded_file_id is None:
                    buf = BufferedInputFile(
                        buffer_bytes,
                        filename=f"attach.{'jpg' if media_type == 'photo' else 'mp4'}",
                    )
                    if media_type == "photo":
                        msg = await bot.send_photo(
                            mid,
                            photo=buf,
                            caption=msg_txt,
                            reply_markup=make_request_kb(request_id),
                            parse_mode="HTML",
                        )
                        uploaded_file_id = msg.photo[-1].file_id
                    else:
                        msg = await bot.send_video(
                            mid,
                            video=buf,
                            caption=msg_txt,
                            reply_markup=make_request_kb(request_id),
                            parse_mode="HTML",
                        )
                        uploaded_file_id = msg.video.file_id
                else:
                    if media_type == "photo":
                        await bot.send_photo(
                            mid,
                            photo=uploaded_file_id,
                            caption=msg_txt,
                            reply_markup=make_request_kb(request_id),
                            parse_mode="HTML",
                        )
                    else:
                        await bot.send_video(
                            mid,
                            video=uploaded_file_id,
                            caption=msg_txt,
                            reply_markup=make_request_kb(request_id),
                            parse_mode="HTML",
                        )
            else:
                await bot.send_message(
                    mid,
                    msg_txt,
                    reply_markup=make_request_kb(request_id),
                    parse_mode="HTML",
                )
        except Exception as e:
            logging.exception(f"Не смог отправить заявку мастеру {mid}: {e}")

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

    master_user_name = master[2]  # full_name из таблицы masters
    master_fullname = master[3]
    master_number = master[4]
    await user_bot.send_message(
        client_id,
        f"🔧 Ваша заявка №{request_id} принята в работу!\n"
        f"Мастер {master_fullname}(@<b>{master_user_name}</b>) скоро свяжется с вами в Telegram."
        f"\nИли можете позвонить мастеру сами: {master_number}",
        parse_mode="HTML",
    )

    # 2) геопин – только теперь
    if latitude is not None and longitude is not None:
        await query.bot.send_location(
            master_id,
            latitude=latitude,
            longitude=longitude,
        )

    from app.database.models import list_active_masters

    other_masters = await list_active_masters()
    admin_ids = await list_admins()

    # Если текущий master_id — админ, то просто ничего не рассылаем:
    if master_id in admin_ids:
        for aid in admin_ids:
            if aid != master_id:
                try:
                    # Важно: в параметрах send_message нужно писать text=<строка>, а не text: <строка>
                    await query.bot.send_message(
                        aid,
                        text=f"Заявка №{request_id} уже принята другим админом."
                    )
                except Exception as e:
                    logging.exception(f"Не смог уведомить мастера {aid}: {e}")

        # убираем кнопки у исходного сообщения и выходим
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logging.exception(f"Не удалось убрать кнопки у заявки {request_id}: {e}")
        return


    other_masters = [
        mid for mid in other_masters
        if mid != master_id
    ]

    for mid in other_masters:
        try:
            # Важно: в параметрах send_message нужно писать text=<строка>, а не text: <строка>
            await query.bot.send_message(
                mid,
                text=f"Заявка №{request_id} уже принята другим мастером."
            )
        except Exception as e:
            logging.exception(f"Не смог уведомить мастера {mid}: {e}")

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
    try:
        await query.message.edit_reply_markup()
    except Exception:
        pass

    client_id = req[1]
    await user_bot.send_message(
        client_id,
        f"❌ Мастер отклонил заявку №{request_id}. Мы ищем другого специалиста.",
    )

    await resend_request_to_masters(request_id, query.bot, exclude=[master_id])
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

    # 1. сразу закрываем заявку
    await complete_request(request_id, master_id)

    # 2. сообщаем МАСТЕРУ
    await query.message.answer(
        "🎉 Заявка завершена. Не забудьте оплатить комиссию командой /pay_commission",
    )
    await query.message.edit_reply_markup()
    await query.answer("Заявка закрыта")

    # 3. просим КЛИЕНТА оценить работу
    client_id = req[1]
    await user_bot.send_message(
        client_id,
        f"🔔 Мастер завершил работу по заявке №{request_id}.",
        reply_markup=make_rating_kb(request_id),
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


# Кнопка «Оплатить комиссию» в меню
@router.message(F.text == "💳 Оплатить комиссию")
async def btn_pay_commission(message: Message):
    await cmd_pay_commission(message)

@router.callback_query(F.data == "pay")
async def cb_pay_commission(query: CallbackQuery):
    master_id = query.from_user.id

    master = await get_master_by_id(master_id)
    if not master or master[7] != 1:            # is_active
        return await query.answer("⛔ Вы не зарегистрированы или заблокированы.", show_alert=True)

    if master[6] == 0:                          # has_debt
        return await query.answer("🟢 У вас нет задолженности.", show_alert=True)

    # обнуляем долг
    await pay_commission(master_id)

    # убираем кнопку из сообщения
    try:
        await query.message.edit_reply_markup()
    except Exception:
        pass

    await query.message.answer("✅ Комиссия оплачена. Вы снова получаете заявки.")
    await query.answer("Спасибо!")


# ─────────────────── /my_requests ───
@router.message(Command("my_requests"))
async def cmd_my_requests(message: Message):
    master_id = message.from_user.id

    master = await get_master_by_id(master_id)
    if not master or master[7] != 1:
        return await message.answer("⛔ Вы не зарегистрированы или заблокированы.")

    requests = await list_master_requests(master_id)

    lines = [f"#{r[0]} — {r[1]}" for r in requests]
    if lines:
        text = "\n".join(lines)
        text = "Ваши текущие заявки:\n" + text
    else:
        text = "У вас нет активных заявок."

    if master[6] == 1:
        text += "\n\n⚠️ Есть задолженность по комиссии. /pay_commission"
    else:
        text += "\n\n🟢 Задолженности по комиссии нет."

    await message.answer(text)


# ─────────────────── /finish_request ───
@router.message(Command("finish_request"))
async def cmd_finish_request(message: Message, state: FSMContext):
    await state.set_state(CloseRequestFSM.request_id)
    await message.answer("Введите номер заявки, которую нужно закрыть:")


@router.message(StateFilter(CloseRequestFSM.request_id), F.text)
async def process_finish_request(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите число — номер заявки.")

    request_id = int(message.text)
    master_id = message.from_user.id

    master = await get_master_by_id(master_id)
    if not master or master[7] != 1:
        await state.clear()
        return await message.answer("⛔ Вы не зарегистрированы или заблокированы.")

    req = await get_request_by_id(request_id)
    if not req or req[10] != "in_progress" or req[11] != master_id:
        await state.clear()
        return await message.answer("⛔ Заявка не у вас в работе.")

    await complete_request(request_id, master_id)
    await state.clear()
    await message.answer(
        "Заявка закрыта. Не забудьте оплатить комиссию командой /pay_commission."
    )

    client_id = req[1]
    await user_bot.send_message(
        client_id,
        f"🔔 Мастер завершил работу по заявке №{request_id}.",
        reply_markup=make_rating_kb(request_id),
        parse_mode="HTML",
    )


# Кнопка «Мои заявки» в меню
@router.message(F.text == "📄 Мои заявки")
async def btn_my_requests(message: Message):
    await cmd_my_requests(message)


# Кнопка «Закрыть по номеру» в меню
@router.message(F.text == "✅ Закрыть по номеру")
async def btn_finish_request_menu(message: Message, state: FSMContext):
    await cmd_finish_request(message, state)

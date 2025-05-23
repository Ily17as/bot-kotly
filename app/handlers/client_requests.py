from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.database.models import save_request, get_user_requests
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from app.database.models import list_available_masters
from app.handlers.master import make_request_kb
from app.database.database import get_db

router = Router()

class RequestForm(StatesGroup):
    description = State()
    media = State()
    location = State()

# --------------- Обработчики создания новой заявки ---------------

@router.message(F.text == "📋 Новая заявка")
async def start_request(message: Message, state: FSMContext):
    await state.set_state(RequestForm.description)
    await message.answer("📝 Пожалуйста, опишите проблему как можно подробнее:\n\n"
                            "- Что за котёл? (марка, модель)\n"
                            "- Как давно началась проблема?\n"
                            "- Какие ошибки или коды показывает панель управления?\n"
                            "- Есть ли утечка воды или газа?\n"
                            "- Наблюдаются ли посторонние шумы или запах?\n\n"
                            "Чем подробнее описание, тем быстрее мастер сможет вам помочь!\n\n"
                            "Отправьте текстовое сообщение 👇",
                            parse_mode="HTML"
                         )

@router.message(RequestForm.description, F.text)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(RequestForm.media)
    await message.answer("📷 Прикрепите фото или видео (один файл)")

@router.message(RequestForm.media, F.photo | F.video)
async def process_media(message: Message, state: FSMContext):
    media_id = message.photo[-1].file_id if message.photo else message.video.file_id
    media_type = 'photo' if message.photo else 'video'

    await state.update_data(media_id=media_id, media_type=media_type)
    await state.set_state(RequestForm.location)
    await message.answer("📍 Теперь отправьте геолокацию или напишите адрес текстом")

@router.message(RequestForm.location, F.location | F.text)
async def process_location(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id

    # формируем контакт: либо @username, либо ссылка tg://user?id=
    if message.from_user.username:
        username = f"@{message.from_user.username}"
    else:
        username = f"<a href='tg://user?id={user_id}'>Профиль</a>"

    description = data['description']
    media_id    = data['media_id']
    media_type  = data['media_type']
    location_text = (
        f"{message.location.latitude}, {message.location.longitude}"
        if message.location
        else message.text
    )

    # 1) единственная вставка — и сразу получаем new_req_id
    db = await get_db()
    cursor = await db.execute(
        """
        INSERT INTO requests
          (user_id, username, description, location,
           media_id, media_type, status, master_id, commission_paid)
        VALUES (?, ?, ?, ?, ?, ?, 'open', NULL, 0)
        """,
        (user_id, username, description, location_text, media_id, media_type)
    )
    new_req_id = cursor.lastrowid
    await db.commit()
    await db.close()
    from app.bot import master_bot

    # 2) рассылаем мастерам
    masters = await list_available_masters()
    for mid in masters:
        await master_bot.send_message(
            chat_id=mid,
            text=(
                f"🆕 Новая заявка №{new_req_id}!\n"
                f"📍 Район: {location_text}\n"
                f"🧾 Проблема: {description}"
            ),
            reply_markup=make_request_kb(new_req_id),
            parse_mode="HTML"
        )

    # 3) подтверждаем клиенту
    finish_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Мои заявки")],
            [KeyboardButton(text="📋 Новая заявка")]
        ], resize_keyboard=True
    )


    await message.answer("✅ Ваша заявка принята и отправлена мастерам!\n\n"
                            "🔎 <b>Что будет дальше:</b>\n"
                            "- Первый свободный мастер свяжется с вами напрямую через Telegram.\n"
                            "- 💬 Вы сами обсуждаете детали, сроки и оплату с мастером.\n"
                            "- Сервис <b>КотёлОК</b> — это агрегатор заявок и <b>не несёт ответственности</b> за выполнение работ.\n\n"
                            "⏳ Если в течение 24 часов вашу заявку никто не примет, она будет автоматически отменена, а деньги за создание вернутся на ваш счёт.\n\n"
                            "Спасибо за использование нашего сервиса! 🔥",
                            reply_markup=finish_keyboard,
                            parse_mode="HTML"
                         )
    await state.clear()

# --------------- Обработчики ошибок ввода ---------------

@router.message(RequestForm.description)
async def invalid_description(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте текстовое описание проблемы!")

@router.message(RequestForm.media)
async def invalid_media(message: Message):
    await message.answer("⚠️ Пожалуйста, прикрепите фото или видео!")

@router.message(RequestForm.location)
async def invalid_location(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте геолокацию или текстовый адрес!")

# --------------- Обработчик просмотра заявок ---------------

@router.message(F.text == "📄 Мои заявки")
async def list_requests(message: Message):
    requests = await get_user_requests(message.from_user.id)
    if not requests:
        await message.answer("У вас пока нет заявок 🙃")
        return

    msg = ["🗂 Ваши заявки:"]
    for req in requests:
        entry = f"\n👤 {req[2]}\n📍 <b>{req[4]}</b>\n📝 {req[3]}\n"
        msg.append(entry)
    await message.answer("\n".join(msg), parse_mode="HTML")
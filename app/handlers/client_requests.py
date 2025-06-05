import asyncio

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database.database import get_db
from app.database.models import get_user_requests, list_available_masters
from app.handlers.master import make_request_kb

from aiogram.types import BufferedInputFile
from io import BytesIO
import logging
from app.database.models import list_admins
from app.bots import master_bot
from app.database.models import get_request_by_id

router = Router()


# ---------------- FSM ----------------
class RequestForm(StatesGroup):
    description = State()
    media = State()
    district = State()
    location = State()


# ---------------- Создание заявки ----------------
@router.message(F.text == "📋 Новая заявка")
async def start_request(message: Message, state: FSMContext):
    await state.set_state(RequestForm.description)
    await message.answer(
        "📝 Пожалуйста, опишите проблему как можно подробнее:\n\n"
        "- Что за котёл? (марка, модель)\n"
        "- Как давно началась проблема?\n"
        "- Какие ошибки или коды показывает панель управления?\n"
        "- Есть ли утечка воды или газа?\n"
        "- Наблюдаются ли посторонние шумы или запах?\n\n"
        "Чем подробнее описание, тем быстрее мастер сможет вам помочь!\n\n"
        "Отправьте текстовое сообщение 👇",
        parse_mode="HTML",
    )


@router.message(RequestForm.description, F.text)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(RequestForm.media)
    await message.answer("📷 Прикрепите фото или видео проблемы (один файл)")


@router.message(RequestForm.media, F.photo | F.video)
async def process_media(message: Message, state: FSMContext):
    media_id = message.photo[-1].file_id if message.photo else message.video.file_id
    media_type = "photo" if message.photo else "video"
    await state.update_data(media_id=media_id, media_type=media_type)
    await state.set_state(RequestForm.district)
    await message.answer("🏙 Укажите пожалуйста район (текстом). "
                         "Например: «Советский», «Приморский» или «Центр»")


@router.message(RequestForm.district, F.text)
async def process_district(message: Message, state: FSMContext):
    await state.update_data(settlement=message.text.strip())   # сохранили
    await state.set_state(RequestForm.location)
    await message.answer("📍 Теперь отправьте точную геолокацию *или* "
                         "напишите адрес одной строкой",
                         parse_mode="Markdown")

async def delayed_to_masters():
    await asyncio.sleep(300)

@router.message(RequestForm.location, F.location | F.text)
async def process_location(message: Message, state: FSMContext):
    # ---------- данные из FSM ----------
    data = await state.get_data()
    settlement = data["settlement"]
    description = data["description"]
    media_id = data["media_id"]
    media_type = data["media_type"]

    # ---------- пользователь ----------
    user_id = message.from_user.id
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else f"<a href='tg://user?id={user_id}'>Профиль</a>"
    )

    # ---------- локация / адрес ----------
    latitude = message.location.latitude if message.location else None
    longitude = message.location.longitude if message.location else None
    location_text = (
        f"{latitude:.6f}, {longitude:.6f}"
        if message.location
        else message.text.strip()
    )

    # ---------- сохраняем в БД ----------
    db = await get_db()
    cursor = await db.execute(
        """
        INSERT INTO requests
              (user_id, username, description,
               settlement, location,
               latitude, longitude,
               media_id, media_type,
               status, commission_paid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', 0)
        """,
        (
            user_id,
            username,
            description,
            settlement,
            location_text,
            latitude,
            longitude,
            media_id,
            media_type,
        ),
    )
    new_req_id = cursor.lastrowid
    await db.commit()
    await db.close()

    # Снимаем состояние до отправки сообщений, чтобы пользователь
    # сразу мог выполнять другие действия и случайные сообщения
    # не создавали дубликаты заявок.
    await state.clear()

    # ---------- готовим рассылку ----------
    from app.bot import master_bot

    masters = await list_available_masters()
    msg_txt = (
                  f"🆕 Новая заявка №{new_req_id}!\n"
                  f"📍 Район: {settlement}\n"
                  f"🧾 Проблема: {description}"
              )[:1024]
    admin_txt = (
                  f"(ADMIN)🆕 Новая заявка №{new_req_id}!\n"
                  f"📍 Район: {settlement}\n"
                  f"🧾 Проблема: {description}"
              )[:1024]

    # ---------- качаем файл только один раз ----------
    buffer_bytes: bytes | None = None
    if media_id:
        file_info = await message.bot.get_file(media_id)
        file_obj = await message.bot.download_file(file_info.file_path)
        buffer_bytes = (
            file_obj.getvalue() if isinstance(file_obj, BytesIO) else file_obj
        )

    uploaded_file_id: str | None = None  # запомним file_id после первого аплоуда
    logging.info(f"Masters to notify: {masters}")

    admin_ids = await list_admins()
    # 1) сразу рассылаем админам
    for aid in admin_ids:
        try:
            # 1️⃣  СНАЧАЛА медиа (если есть)
            if buffer_bytes:
                if uploaded_file_id is None:
                    # ─ первая отправка – реальный аплоуд
                    buf = BufferedInputFile(
                        buffer_bytes,
                        filename=f"attach.{'jpg' if media_type == 'photo' else 'mp4'}",
                    )
                    if media_type == "photo":
                        msg = await master_bot.send_photo(
                            aid,
                            photo=buf,
                            caption=admin_txt,
                            reply_markup=make_request_kb(new_req_id),
                            parse_mode="HTML",
                        )
                        uploaded_file_id = msg.photo[-1].file_id
                    else:
                        msg = await master_bot.send_video(
                            aid,
                            video=buf,
                            caption=admin_txt,
                            reply_markup=make_request_kb(new_req_id),
                            parse_mode="HTML",
                        )
                        uploaded_file_id = msg.video.file_id
                else:
                    # ─ остальным мастерам – по file_id
                    if media_type == "photo":
                        await master_bot.send_photo(
                            aid,
                            photo=uploaded_file_id,
                            caption=admin_txt,
                            reply_markup=make_request_kb(new_req_id),
                            parse_mode="HTML",
                        )
                    else:
                        await master_bot.send_video(
                            aid,
                            video=uploaded_file_id,
                            caption=admin_txt,
                            reply_markup=make_request_kb(new_req_id),
                            parse_mode="HTML",
                        )
            else:
                # если медиа нет – сразу текст
                await master_bot.send_message(
                    aid,
                    admin_txt,
                    reply_markup=make_request_kb(new_req_id),
                    parse_mode="HTML",
                )

            logging.info(f"Masters to notify: {masters}")

        except Exception as e:
            logging.exception(f"Не смог отправить заявку мастеру {aid}: {e}")


    finish_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Мои заявки")],
            [KeyboardButton(text="📋 Новая заявка")],
        ],
        resize_keyboard=True,
    )

    await message.answer(
        "✅ Ваша заявка принята и отправлена мастерам!\n\n"
        "🔎 <b>Что будет дальше:</b>\n"
        "- Первый свободный мастер свяжется с вами напрямую через Telegram.\n"
        "- 💬 Вы сами обсуждаете детали, сроки и оплату с мастером.\n"
        "- Сервис <b>КотёлОК</b> — агрегатор заявок и <b>не несёт ответственности</b> за выполнение работ.\n\n"
        "⏳ Если в течение 24 часов вашу заявку никто не примет, она будет автоматически отменена.\n\n"
        "Спасибо за использование нашего сервиса! 🔥",
        reply_markup=finish_keyboard,
        parse_mode="HTML",
    )

    # Завершаем FSM сразу после создания заявки, иначе пользователь
    # не сможет начать новый диалог в течение минуты ожидания.
    await state.clear()

    await asyncio.sleep(60)

    other_masters = [
        mid for mid in masters
        if mid not in admin_ids
    ]

    req = await get_request_by_id(new_req_id)
    if not req or req[10] != "open":
        pass
    else:
        for mid in other_masters:
            try:
                # 1️⃣  СНАЧАЛА медиа (если есть)
                if buffer_bytes:
                    if uploaded_file_id is None:
                        # ─ первая отправка – реальный аплоуд
                        buf = BufferedInputFile(
                            buffer_bytes,
                            filename=f"attach.{'jpg' if media_type == 'photo' else 'mp4'}",
                        )
                        if media_type == "photo":
                            msg = await master_bot.send_photo(
                                mid,
                                photo=buf,
                                caption=msg_txt,
                                reply_markup=make_request_kb(new_req_id),
                                parse_mode="HTML",
                            )
                            uploaded_file_id = msg.photo[-1].file_id
                        else:
                            msg = await master_bot.send_video(
                                mid,
                                video=buf,
                                caption=msg_txt,
                                reply_markup=make_request_kb(new_req_id),
                                parse_mode="HTML",
                            )
                            uploaded_file_id = msg.video.file_id
                    else:
                        # ─ остальным мастерам – по file_id
                        if media_type == "photo":
                            await master_bot.send_photo(
                                mid,
                                photo=uploaded_file_id,
                                caption=msg_txt,
                                reply_markup=make_request_kb(new_req_id),
                                parse_mode="HTML",
                            )
                        else:
                            await master_bot.send_video(
                                mid,
                                video=uploaded_file_id,
                                caption=msg_txt,
                                reply_markup=make_request_kb(new_req_id),
                                parse_mode="HTML",
                            )
                else:
                    # если медиа нет – сразу текст
                    await master_bot.send_message(
                        mid,
                        msg_txt,
                        reply_markup=make_request_kb(new_req_id),
                        parse_mode="HTML",
                    )

                logging.info(f"Masters to notify: {masters}")

            except Exception as e:
                logging.exception(f"Не смог отправить заявку мастеру {mid}: {e}")

# ---------------- валидаторы ----------------
@router.message(RequestForm.description)
async def invalid_description(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте текстовое описание проблемы!")


@router.message(RequestForm.media)
async def invalid_media(message: Message):
    await message.answer("⚠️ Пожалуйста, прикрепите фото или видео!")


@router.message(RequestForm.district)
async def invalid_district(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте название района текстом!")


@router.message(RequestForm.location)
async def invalid_location(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте геолокацию или текстовый адрес!")


# ---------------- просмотр своих заявок ----------------
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

# handlers/client_requests.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.database.models import save_request, get_user_requests

router = Router()

class RequestForm(StatesGroup):
    description = State()
    location = State()
    media = State()

@router.message(F.text == "📋 Новая заявка")
async def start_request(message: Message, state: FSMContext):
    await state.set_state(RequestForm.description)
    await message.answer("📝 Опишите проблему (что случилось?)")

@router.message(RequestForm.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(RequestForm.location)
    await message.answer("📍 Отправьте геолокацию (локацией или текстом адреса)")

@router.message(RequestForm.location)
async def process_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(RequestForm.media)
    await message.answer("📷 Прикрепите фото или видео (один файл)")

@router.message(RequestForm.media, F.photo | F.video)
async def process_media(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    description = data['description']
    location = data['location']
    media_id = message.photo[-1].file_id if message.photo else message.video.file_id
    media_type = 'photo' if message.photo else 'video'

    await save_request(user_id, description, location, media_id, media_type)
    await message.answer("✅ Заявка принята и сохранена!")
    await state.clear()

@router.message(F.text == "📄 Мои заявки")
async def list_requests(message: Message):
    requests = await get_user_requests(message.from_user.id)
    if not requests:
        await message.answer("У вас пока нет заявок 🙃")
        return

    msg = ["🗂 Ваши заявки:"]
    for req in requests:
        entry = f"\n📍 <b>{req[3]}</b>\n📝 {req[2]}\n"
        msg.append(entry)
    await message.answer("\n".join(msg), parse_mode="HTML")

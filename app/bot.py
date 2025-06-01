import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message

from app.config import BOT_TOKEN, MASTER_BOT_TOKEN
from app.database.database import init_db
from app.database.models import add_user, list_users
from app.handlers.client_requests import router as client_router
from app.handlers.master import router as master_router
from app.middlewares.error_handler import ErrorHandlerMiddleware
from app.utils.logger import setup_logger
from aiogram.client.bot import DefaultBotProperties

from app.handlers.client_confirm import router as confirm_router
from app.handlers import client_review

# — общий логгер
setup_logger()
logger = logging.getLogger(__name__)

# === Клиентский бот ===
user_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
user_dp = Dispatcher()
user_dp.include_router(client_router)
user_dp.message.middleware(ErrorHandlerMiddleware())
user_dp.include_router(confirm_router)

# === Мастер-бот ===
master_bot = Bot(token=MASTER_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
master_dp = Dispatcher()
master_dp.include_router(master_router)
master_dp.message.middleware(ErrorHandlerMiddleware())

from app.handlers import client_review
user_dp.include_router(client_review.router)

# Экспорт, чтобы client_requests.py мог шлать мастерам
__all__ = ["user_bot", "master_bot"]

# /start для клиента
main_router = Router()
main_router.message.filter(Command("start"))

# Команда /start
@main_router.message(Command("start"))
async def start_handler(message: Message):
    await add_user(message.from_user.id, message.from_user.username or "")

    # Кнопки
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Новая заявка")],
            [KeyboardButton(text="📄 Мои заявки")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "👋 Добро пожаловать в сервис заявок <b>КотёлОК</b>!\n\n"
        "Здесь вы можете создать заявку на ремонт, диагностику или обслуживание котлов.\n\n"
        "🛠 <b>Что можно сделать:</b>\n"
        "- 📋 Оформить новую заявку\n"
        "- 📄 Посмотреть свои текущие заявки\n\n"
        "💬 <b>Как оформить заявку:</b>\n"
        "1. Кратко опишите проблему с котлом.\n"
        "2. Прикрепите фото или видео (если возможно).\n"
        "3. Укажите место (адрес или отправьте геолокацию).\n\n"
        "❗ После оформления:\n"
        "- Заявка попадёт в очередь.\n"
        "- Первый свободный мастер свяжется с вами через Telegram.\n"
        "- 💬 <b>Оплата и детали работы</b> обговариваются напрямую с мастером.\n"
        "- Сервис <b>не несёт ответственности</b> за выполнение работ — мы только агрегатор.\n\n"
        "⏳ Если в течение 24 часов вашу заявку никто не примет, она будет отменена, а деньги за создание вернутся.\n\n"
        "✅ Чтобы начать — нажмите кнопку \"📋 Новая заявка\" ниже!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


user_dp.include_router(main_router)

# Отладка пользователей
async def debug_users():
    users = await list_users()
    for u in users:
        print(f"ID: {u[0]}, Username: {u[1]}")

# Запуск обоих ботов
async def main():
    await init_db()
    logger.info("✅ База инициализирована; запускаем оба бота")
    await asyncio.gather(
        user_dp.start_polling(user_bot, drop_pending_updates=True),
        master_dp.start_polling(master_bot, drop_pending_updates=True),
    )

if __name__ == "__main__":
    asyncio.run(main())

import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from app.config import BOT_TOKEN
from app.database.database import init_db
from app.database.models import add_user, list_users
from app.handlers.client_requests import router as request_router
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from app.middlewares.error_handler import ErrorHandlerMiddleware
from app.utils.logger import setup_logger

logger = logging.getLogger(__name__)
setup_logger()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
bot.parse_mode = ParseMode.HTML

dp = Dispatcher()
main_router = Router()
dp.include_router(main_router)
dp.include_router(request_router)  # FSM-заявки
dp.message.middleware(ErrorHandlerMiddleware())

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


# Тестовая команда для вывода пользователей в консоль
async def debug_users():
    users = await list_users()
    for u in users:
        print(f"ID: {u[0]}, Username: {u[1]}")

# Основной запуск
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)  # Удаляем webhook
    logger.info("Бот запущен и подключен к SQLite базе данных.")
    await debug_users()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

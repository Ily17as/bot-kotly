# Создаёт два независимых экземпляра Bot и ничего больше.
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from app.config import BOT_TOKEN, MASTER_BOT_TOKEN

user_bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

master_bot = Bot(
    token=MASTER_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
import logging
import traceback

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error("❌ Ошибка в обработчике:\n%s", traceback.format_exc())
            if hasattr(event, "answer"):
                await event.answer("⚠️ Произошла ошибка. Попробуйте позже.")
            # Не пробрасываем дальше — просто глотаем

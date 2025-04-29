import logging
import os

def setup_logger():
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))
    os.makedirs(log_dir, exist_ok=True)

    # Создаем базовый логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Файловый обработчик
    file_handler = logging.FileHandler(os.path.join(log_dir, 'bot.log'), mode='a', encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    # Добавляем обработчики
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
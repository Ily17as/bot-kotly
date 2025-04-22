import logging
import os

def setup_logger():
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        filename=os.path.join(log_dir, 'bot.log'),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

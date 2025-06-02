import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "..", "database.db"))
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")   # из BotFather
COMMISSION_CURRENCY    = os.getenv("COMMISSION_CURRENCY", "RUB")
COMMISSION_AMOUNT_RUB  = int(os.getenv("COMMISSION_AMOUNT", "100"))  # целые рубли

# Telegram ждёт «копейки», поэтому:
COMMISSION_AMOUNT_MINOR = COMMISSION_AMOUNT_RUB * 100
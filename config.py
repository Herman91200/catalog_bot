import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")         # ← берётся из хостинга
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))     # ← берётся из хостинга
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0")) # ← берётся из хостинга

DB_PATH = "data/catalog.db"
LOG_PATH = "bot.log"

if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения хостинга!")
if not ADMIN_ID:
    raise ValueError("Не задан ADMIN_ID в переменных окружения хостинга!")

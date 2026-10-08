# config.py
# Настройки читаются из переменных окружения хостинга.
# Токен и ID ты вписываешь в панели хостинга, а не тут.

import os

# --- Из переменных окружения хостинга ---
BOT_TOKEN = os.getenv("8610465394:AAGodtZAUxHBNTOlgFaKR0YeY87p6towgyQ", "")
ADMIN_ID = int(os.getenv("8415618845", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

# --- Файлы (оставляем в коде) ---
DB_PATH = "data/catalog.db"
LOG_PATH = "bot.log"

# --- Простая проверка: если ключей нет — падаем с понятной ошибкой ---
if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения хостинга!")
if not ADMIN_ID:
    raise ValueError("Не задан ADMIN_ID в переменных окружения хостинга!")
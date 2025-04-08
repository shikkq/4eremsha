import os
import asyncio
import threading
from flask import Flask, request
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from bot import dp  # Dispatcher с зарегистрированными хендлерами
from vk_parser import run_parser

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render подставит это

# Flask и aiogram
app = Flask(__name__)
bot = Bot(token=TOKEN)
storage = MemoryStorage()

# Telegram webhook
@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def telegram_webhook():
    try:
        json_data = request.get_data().decode("utf-8")
        update = Update.model_validate_json(json_data)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(dp.feed_update(bot, update))
    except Exception as e:
        print(f"Ошибка обработки webhook: {e}")
    return "ok", 200

# Эндпоинт для парсера (вызывается Cron-job.org)
@app.route("/run-parser")
def parser_runner():
    try:
        run_parser()
        return "Парсер успешно запущен", 200
    except Exception as e:
        return f"Ошибка запуска парсера: {e}", 500

@app.route("/")
def index():
    return "Bot is running!", 200

@app.route("/ping")
def ping():
    return "pong", 200

# Установка webhook при старте
async def on_startup():
    if RENDER_URL:
        await bot.set_webhook(f"{RENDER_URL}/webhook/{WEBHOOK_SECRET}")
        print(f"✅ Webhook установлен: {RENDER_URL}/webhook/{WEBHOOK_SECRET}")
    else:
        print("❌ Не задан RENDER_EXTERNAL_URL")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_until_complete, args=(on_startup(),)).start()
    app.run(host="0.0.0.0", port=10000)

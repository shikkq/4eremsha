import os
import asyncio
from flask import Flask, request
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from bot import dp  # Dispatcher с зарегистрированными хендлерами
from vk_parser import run_parser

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://yourapp.onrender.com/webhook

# Инициализация Flask и бота
app = Flask(__name__)
bot = Bot(token=TOKEN)
storage = MemoryStorage()

@app.route("/", methods=["GET"])
def index():
    return "OK", 200

@app.route("/ping")
def ping():
    return "OK", 200

@app.route("/run-parser")
def parser_runner():
    try:
        run_parser()
        return "Парсер успешно запущен", 200
    except Exception as e:
        return f"Ошибка запуска парсера: {e}", 500

@app.route("/webhook", methods=["POST"])
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

# Установка webhook при запуске
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_startup())
    app.run(host="0.0.0.0", port=10000)

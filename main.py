import os
import asyncio
from flask import Flask, request
from dotenv import load_dotenv
from aiogram import Bot, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from bot import dp  # Dispatcher с зарегистрированными хендлерами
from vk_parser import run_parser

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Инициализация бота и Flask
bot = Bot(token=TOKEN)
storage = MemoryStorage()
app = Flask(__name__)

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

@app.route("/", methods=["POST"])
def telegram_webhook():
    try:
        json_data = request.get_data().decode("utf-8")
        update = Update.model_validate_json(json_data)
        asyncio.create_task(dp.feed_update(bot, update))
    except Exception as e:
        print(f"Ошибка обработки webhook: {e}")
    return "ok", 200

# Установка webhook при старте
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook установлен: {WEBHOOK_URL}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_startup())
    app.run(host="0.0.0.0", port=10000)

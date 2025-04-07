import os
import asyncio
from flask import Flask, request
from dotenv import load_dotenv
from aiogram import Bot, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from bot import dp  # импорт aiogram.Dispatcher
from vk_parser import run_parser  # функция запуска парсера

# Загрузка .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://yourapp.onrender.com/webhook

# Инициализация
bot = Bot(token=TOKEN)
storage = MemoryStorage()

# Flask-приложение
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

@app.post("/webhook")
def webhook():
    try:
        update = Update.model_validate_json(request.get_data().decode("utf-8"))
        asyncio.run(dp.feed_update(bot, update))
    except Exception as e:
        print(f"Ошибка обработки webhook: {e}")
    return "ok", 200

# Установка webhook при старте
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print("Webhook установлен:", WEBHOOK_URL)

if __name__ == "__main__":
    asyncio.run(on_startup())  # Устанавливаем webhook
    app.run(host="0.0.0.0", port=10000)

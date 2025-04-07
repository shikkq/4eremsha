# app.py
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from bot import dp  # тут уже подключены все handlers
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")

bot = Bot(token=TOKEN)
app = Flask(__name__)

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def telegram_webhook():
    update = Update.model_validate(request.json)
    await dp.feed_update(bot, update)
    return "ok"

@app.route("/")
def root():
    return "Bot is running!"

# Установка webhook (один раз при запуске)
@app.before_first_request
async def setup_webhook():
    domain = os.getenv("RENDER_EXTERNAL_URL")  # Render установит эту переменную
    await bot.set_webhook(f"{domain}/webhook/{WEBHOOK_SECRET}")

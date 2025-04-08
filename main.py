import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from bot import dp
from run_parser import update_all_cities

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "supersecret")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

# FastAPI и aiogram
app = FastAPI()
bot = Bot(token=TOKEN)
storage = MemoryStorage()

@app.post(f"/webhook/{WEBHOOK_URL}")
async def telegram_webhook(request: Request):
    try:
        body = await request.body()
        update = Update.model_validate_json(body.decode("utf-8"))
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"Ошибка обработки webhook: {e}")
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Hello from FastAPI"}

@app.get("/ping")
def ping():
    return {"pong": True}

@app.get("/run-parser")
def run_parser_route():
    try:
        update_all_cities()  # Вызываем её вместо run_parser
        return {"status": "Парсинг завершён"}
    except Exception as e:
        return {"error": str(e)}

@app.on_event("startup")
async def on_startup():
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook/{WEBHOOK_URL}"
        await bot.set_webhook(webhook_url)
        print(f"✅ Webhook установлен: {webhook_url}")
    else:
        print("❌ Не задан RENDER_EXTERNAL_URL")

print(f"🌐 Starting app on port: {os.environ.get('PORT')}")

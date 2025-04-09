import uvicorn
import os
from dotenv import load_dotenv
from threading import Thread
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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

# Инициализация aiogram компонентов
bot = Bot(token=TOKEN)
storage = MemoryStorage()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook/{WEBHOOK_URL}"
        await bot.set_webhook(webhook_url)
        print(f"✅ Webhook установлен: {webhook_url}")
    else:
        print("❌ Не задан RENDER_EXTERNAL_URL")
    yield  # тут может быть логика завершения (on shutdown)

# Инициализация FastAPI
app = FastAPI(lifespan=lifespan)

# Webhook-обработчик
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
        Thread(target=update_all_cities).start()
        return {"status": "Парсинг запущен"}
    except Exception as e:
        return {"error": str(e)}

print(f"🌐 Starting app on port: {os.environ.get('PORT')}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🌐 Starting app on port: {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

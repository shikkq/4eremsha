import os
import time
from threading import Thread
from dotenv import load_dotenv
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
PORT = int(os.getenv("PORT", "10000"))

# Пусть к файлу последнего запуска
LAST_RUN_FILE = "last_run.txt"
MIN_INTERVAL_SECONDS = 60 * 30  # 30 минут

# Инициализация компонентов
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
    yield  # On shutdown logic можно добавить здесь

app = FastAPI(lifespan=lifespan)

@app.post(f"/webhook/{WEBHOOK_URL}")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"[!] Ошибка обработки webhook: {e}")
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
        now = time.time()

        # Проверка времени последнего запуска
        if os.path.exists(LAST_RUN_FILE):
            with open(LAST_RUN_FILE, "r") as f:
                last_run = float(f.read().strip() or 0)
            if now - last_run < MIN_INTERVAL_SECONDS:
                return {"status": "Пропущено — парсер недавно запускался."}

        # Обновляем метку времени
        with open(LAST_RUN_FILE, "w") as f:
            f.write(str(now))

        # Запуск парсера в фоне
        Thread(target=update_all_cities).start()
        return {"status": "Парсинг запущен"}
    except Exception as e:
        return {"error": str(e)}

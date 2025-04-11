import os
import time
from threading import Thread, Lock
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

# Путь к файлу последнего запуска и минимальный интервал (30 мин)
LAST_RUN_FILE = "last_run.txt"
MIN_INTERVAL_SECONDS = 60 * 30  # 30 минут

# Глобальная блокировка для парсера
parser_lock = Lock()

# Инициализация компонентов
bot = Bot(token=TOKEN)
storage = MemoryStorage()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook/{WEBHOOK_URL}"
        try:
            await bot.set_webhook(webhook_url)
            print(f"✅ Webhook установлен: {webhook_url}")
        except Exception as e:
            print(f"[!] Ошибка установки webhook в lifespan: {e}")
    else:
        print("❌ Не задан RENDER_EXTERNAL_URL")
    yield  # Можно добавить логику при завершении

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
async def ping():
    # Обновляем webhook в фоновом режиме как резерв, не блокируя обработку запроса
    try:
        webhook_url = f"{RENDER_URL}/webhook/{WEBHOOK_URL}"
        # Создаем задачу для обновления вебхука
        _ =  asyncio.create_task(bot.set_webhook(webhook_url))
    except Exception as e:
        print(f"Ошибка установки webhook в /ping: {e}")
    return {"pong": True}

@app.get("/run-parser")
def run_parser_route():
    try:
        now = time.time()

        # Проверка времени последнего запуска через файл
        if os.path.exists(LAST_RUN_FILE):
            with open(LAST_RUN_FILE, "r") as f:
                last_run = float(f.read().strip() or 0)
            if now - last_run < MIN_INTERVAL_SECONDS:
                return {"status": "Пропущено — парсер недавно запускался."}

        # Зафиксировать время запуска
        with open(LAST_RUN_FILE, "w") as f:
            f.write(str(now))

        # Если парсер уже запущен, не запускаем повторно
        if parser_lock.locked():
            return {"status": "Парсер уже запущен."}

        # Функция-обёртка, запускающая парсер под блокировкой
        def run_parser():
            with parser_lock:
                print("⏳ Парсер стартовал...")
                update_all_cities()
                print("✅ Парсер завершил работу.")

        # Запуск фонового потока (daemon=True, чтобы поток завершался вместе с процессом)
        Thread(target=run_parser, daemon=True).start()
        return {"status": "Парсинг запущен"}
    except Exception as e:
        return {"error": str(e)}

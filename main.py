import asyncio
import sqlite3
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command

from database import init_db
from vk_parser import search_vk_groups

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")

VK_KEYWORDS = os.getenv("VK_KEYWORDS", "").split(",")
DB_PATH = "shelters.db"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
init_db()

CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань"]
user_city = {}  # user_id -> city


@dp.message(Command("start"))
async def start_handler(message: Message):
    buttons = [[KeyboardButton(text=city)] for city in CITIES]
    buttons.append([KeyboardButton(text="Другой город")])

    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

    await message.answer("Привет! Выберите город, чтобы найти приюты, которым нужна помощь:", reply_markup=keyboard)


@dp.message(lambda message: message.text in CITIES or message.text == "Другой город")
async def handle_city_choice(message: Message):
    user_id = message.from_user.id
    city = message.text

    if city == "Другой город":
        await message.answer("Введите название города вручную:")
        return

    user_city[user_id] = city
    await message.answer(f"Ищем приюты в городе {city}, подождите немного...")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name FROM shelters WHERE city=?", (city,))
    shelters = c.fetchall()
    conn.close()

    if not shelters:
        await message.answer("К сожалению, ничего не найдено.")
        return

    keyboard = InlineKeyboardMarkup()
    for sid, name in shelters[:10]:
        keyboard.add(InlineKeyboardButton(text=name, callback_data=f"info_{sid}"))

    await message.answer("Вот, что удалось найти:", reply_markup=keyboard)


@dp.callback_query(lambda call: call.data.startswith("info_"))
async def show_info(callback: types.CallbackQuery):
    shelter_id = callback.data[5:]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, link, info FROM shelters WHERE id=?", (shelter_id,))
    row = c.fetchone()
    conn.close()

    if row:
        name, link, info = row
        msg = f"<b>{name}</b>\n{link}\n\n{info}"
        await callback.message.answer(msg, parse_mode="HTML")
    else:
        await callback.message.answer("Не удалось найти информацию.")

    await callback.answer()


@dp.message(lambda m: m.text in ["🔧 Волонтёрство", "📦 Сбор"])
async def choose_filter(message: Message):
    city = user_city.get(message.from_user.id)
    if not city:
        await message.answer("Сначала выберите или введите город.")
        return

    selected_type = message.text
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, info FROM shelters WHERE city=?", (city,))
    shelters = c.fetchall()
    conn.close()

    if not shelters:
        await message.answer("Ничего не нашлось.")
        return

    filtered = []
    for sid, name, info in shelters:
        info_lower = info.lower()
        if selected_type == "🔧 Волонтёрство" and any(word in info_lower for word in ["волонтёр", "приходите", "помочь"]):
            filtered.append((sid, name))
        elif selected_type == "📦 Сбор" and any(word in info_lower for word in ["корм", "лекарства", "сбор", "деньги"]):
            filtered.append((sid, name))

    if not filtered:
        await message.answer("По этому фильтру ничего не найдено.")
        return

    keyboard = InlineKeyboardMarkup()
    for shelter_id, name in filtered[:10]:
        keyboard.add(InlineKeyboardButton(text=name, callback_data=f"info_{shelter_id}"))

    await message.answer("Вот, что удалось найти:", reply_markup=keyboard)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import sqlite3
from aiogram import Dispatcher, types, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command

from database import (
    init_db, get_shelters_for_city, add_favorite,
    get_user_favorites, get_recent_posts_for_group
)

init_db()
dp = Dispatcher()
CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань"]
user_city: dict[int, str] = {}

@dp.message(Command("start"))
async def start_handler(message: Message):
    buttons = [[KeyboardButton(text=city)] for city in CITIES]
    buttons.append([KeyboardButton(text="Другой город")])
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

    await message.answer(
        "Привет! Выберите город, чтобы найти приюты, которым нужна помощь:",
        reply_markup=keyboard
    )

@dp.message(lambda m: m.text in CITIES or m.text == "Другой город")
async def handle_city_choice(message: Message):
    user_id = message.from_user.id
    city = message.text

    if city == "Другой город":
        await message.answer("Введите название города вручную:")
        return

    user_city[user_id] = city
    await message.answer(f"Ищем приюты в городе {city}, подождите немного...")
    await show_shelters(message, city)

@dp.message(lambda m: m.text and m.from_user.id in user_city and m.text not in CITIES)
async def handle_custom_city(message: Message):
    city = message.text.strip()
    user_city[message.from_user.id] = city
    await message.answer(f"Ищем приюты в городе {city}, подождите немного...")
    await show_shelters(message, city)

async def show_shelters(message: Message, city: str):
    shelters = get_shelters_for_city(city)

    if not shelters:
        await message.answer("К сожалению, ничего не найдено.")
        return

    for shelter in shelters:
        text = f"<b>{shelter[1]}</b>\n\n{(shelter[4] or '')}\n\n🔗 {shelter[2]}"
        if len(text) > 4096:
            text = text[:4093] + "..."
        button = InlineKeyboardMarkup().add(
            InlineKeyboardButton("⭐ В избранное", callback_data=f"fav|{shelter[0]}|{shelter[2]}")
        )
        await message.answer(text, reply_markup=button, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("info_"))
async def show_info(callback: types.CallbackQuery):
    shelter_id = callback.data[5:]

    conn = sqlite3.connect("shelters.db")
    c = conn.cursor()
    c.execute("SELECT name, link, info FROM shelters WHERE id=?", (shelter_id,))
    row = c.fetchone()
    conn.close()

    if row:
        name, link, info = row
        msg = f"<b>{name}</b>\n{link}\n\n{info}"
        if len(msg) > 4096:
            msg = msg[:4093] + "..."
        await callback.message.answer(msg, parse_mode="HTML")
    else:
        await callback.message.answer("Не удалось найти информацию.")

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("fav|"))
async def add_to_favorites(callback: types.CallbackQuery):
    _, group_id, post_url = callback.data.split("|")
    user_id = callback.from_user.id

    add_favorite(user_id, post_url, group_id)
    await callback.answer("Добавлено в избранное! ⭐")

def get_favorite_shelter_markup(group_id: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🆕 Свежие посты приюта", callback_data=f"recent_posts_{group_id}"))
    return markup

@dp.message(Command("favorites"))
async def show_favorites(message: Message):
    user_id = message.from_user.id
    favorites = get_user_favorites(user_id)

    if not favorites:
        await message.reply("У вас нет избранных постов.")
        return

    for post_url, group_id in favorites:
        await message.answer(f"🔗 {post_url}", reply_markup=get_favorite_shelter_markup(group_id))

@dp.callback_query(lambda c: c.data.startswith("recent_posts_"))
async def handle_recent_posts(callback_query: types.CallbackQuery):
    group_id = callback_query.data.replace("recent_posts_", "")
    posts = get_recent_posts_for_group(group_id)

    if posts:
        for url, text in posts:
            msg = f"{text}\n\n🔗 {url}"
            if len(msg) > 4096:
                msg = msg[:4093] + "..."
            await callback_query.message.answer(msg)
    else:
        await callback_query.message.answer("Нет свежих постов за последние 7 дней 😿")

    await callback_query.answer()

@dp.message(lambda m: m.text in ["🔧 Волонтёрство", "📦 Сбор"])
async def choose_filter(message: Message):
    city = user_city.get(message.from_user.id)
    if not city:
        await message.answer("Сначала выберите или введите город.")
        return

    selected_type = message.text
    filtered = []

    conn = sqlite3.connect("shelters.db")
    c = conn.cursor()
    c.execute("SELECT id, name, info FROM shelters WHERE city=?", (city,))
    shelters = c.fetchall()
    conn.close()

    for sid, name, info in shelters:
        info_lower = (info or "").lower()
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

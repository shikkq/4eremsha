from aiogram import Dispatcher, types, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from database import (
    init_db, get_shelters_for_city, save_post, get_user_saved_posts,
    get_shelter_by_id, add_user_city
)
import asyncio
import re
from datetime import datetime

init_db()
dp = Dispatcher()

CITIES = ["Новосибирск"]
user_city: dict[int, str] = {}
user_last_msg: dict[int, int] = {}

# Утилиты
def days_ago(date_str: str) -> str:
    try:
        post_date = datetime.strptime(date_str, "%Y-%m-%d")
        days = (datetime.now() - post_date).days
        return f"{days} дней назад" if days != 0 else "сегодня"
    except:
        return "дата неизвестна"

def linkify_address(text: str) -> str:
    if not text:
        return "Адрес не указан"
    return f"<a href='https://yandex.ru/maps/?text={text}'>{text}</a>"

def detect_urgency(text: str) -> str:
    if re.search(r"срочн", text, re.IGNORECASE):
        return "🔥 Срочно"
    elif re.search(r"не срочн|можно позже", text, re.IGNORECASE):
        return "⏱ Не срочно"
    else:
        return "❔ Не указано"

# Команды
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "Привет! Выберите город, чтобы найти приюты:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                *[[KeyboardButton(text=city)] for city in CITIES],
                [KeyboardButton(text="Другой город")]
            ],
            resize_keyboard=True
        )
    )

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "📌 /start — выбрать город\n"
        "📍 /near — приюты рядом\n"
        "💾 /fav — сохранённые посты\n"
        "ℹ️ /about — о проекте"
    )

@dp.message(Command("about"))
async def about_handler(message: Message):
    await message.answer("Этот бот — часть школьного социального проекта. "
                         "Он помогает волонтёрам находить приюты, "
                         "которым нужна помощь, и отслеживать актуальные посты.")

@dp.message(Command("near"))
async def near_handler(message: Message):
    await message.answer("🔍 Поиск ближайших приютов в разработке...")

@dp.message(Command("fav"))
async def show_favorites(message: Message):
    user_id = message.from_user.id
    saved = get_user_saved_posts(user_id)
    if not saved:
        await message.reply("У вас пока нет сохранённых постов.")
        return
    for url, text in saved:
        await message.answer(f"🔗 <a href='{url}'>Ссылка на пост</a>\n\n{text}",
                             parse_mode="HTML", disable_web_page_preview=True)

@dp.message(lambda m: m.text in CITIES or m.text == "Другой город")
async def handle_city_choice(message: Message):
    city = message.text
    user_city[message.from_user.id] = city
    if city == "Другой город":
        await message.answer("Введите название города вручную:")
    else:
        await show_shelters(message, city)

@dp.message(lambda m: m.text and m.from_user.id in user_city and m.text not in CITIES)
async def handle_custom_city(message: Message):
    city = message.text.strip()
    user_city[message.from_user.id] = city
    add_user_city(message.from_user.id, city)
    await show_shelters(message, city)

async def show_shelters(message: Message, city: str):
    shelters = get_shelters_for_city(city)

    if not shelters:
        await message.answer(f"Пока нет информации по городу {city}. Ищем...")
        try:
            from vk_parser import search_vk_groups
            await asyncio.to_thread(search_vk_groups, city)
        except Exception as e:
            await message.answer("⚠️ Ошибка парсинга.")
            print("Ошибка:", e)

        for _ in range(5):
            await asyncio.sleep(2)
            shelters = get_shelters_for_city(city)
            if shelters:
                break

        if not shelters:
            await message.answer("Ничего не найдено, попробуйте позже.")
            return

    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"info_{shelter_id}")]
        for shelter_id, name, *_ in shelters
    ]
    await message.answer("📋 Список приютов:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(lambda c: c.data.startswith("info_"))
async def show_info(callback: types.CallbackQuery):
    shelter_id = callback.data[5:]
    row = get_shelter_by_id(shelter_id)
    if not row:
        await callback.message.answer("Информация не найдена.")
        return

    name, link, info, post_date = row
    urgency = detect_urgency(info or "")
    address_match = re.search(r"(ул\.|улица|проспект|д\.\s?\d+|город\s.+)", info or "", re.IGNORECASE)
    address = address_match.group(0) if address_match else ""
    address_link = linkify_address(address)
    contacts = "\n".join(re.findall(r"(?:\+7|8)\d{10}|\b@\w+|\bhttps?://\S+", info or "")) or "Контакты не найдены"
    days = days_ago(post_date or "")

    msg = (
        f"<b>{name}</b>\n"
        f"{link}\n"
        f"⏳ <i>{days}</i>\n"
        f"🏷 <b>{urgency}</b>\n"
        f"📍 {address_link}\n"
        f"📞 {contacts}"
    )

    button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data=f"fav|{shelter_id}|{link}")]
    ])

    user_id = callback.from_user.id
    if user_id in user_last_msg:
        try:
            await callback.message.bot.delete_message(callback.message.chat.id, user_last_msg[user_id])
        except:
            pass

    sent = await callback.message.answer(msg, reply_markup=button, parse_mode="HTML", disable_web_page_preview=True)
    user_last_msg[user_id] = sent.message_id
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("fav|"))
async def add_to_favorites(callback: types.CallbackQuery):
    _, shelter_id, post_url = callback.data.split("|")
    row = get_shelter_by_id(shelter_id)
    if row:
        name, _, info, _ = row
        text = f"{name}\n\n{info[:300]}..." if info else name
        save_post(callback.from_user.id, post_url, shelter_id, text)
    await callback.answer("💾 Сохранено.")

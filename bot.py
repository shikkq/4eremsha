from aiogram import Dispatcher, types
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from database import (
    init_db, get_shelters_for_city, save_post, get_user_saved_posts,
    get_shelter_by_id, add_user_city
)
from vk_parser import extract_address  # Импортируем новый парсер адресов
import asyncio
import re
from datetime import datetime
from urllib.parse import quote

init_db()
dp = Dispatcher()

CITIES = ["Новосибирск"]
user_city: dict[int, str] = {}
user_last_msg: dict[int, int] = {}

# Утилиты
def days_ago(date_str: str) -> str:
    try:
        post_date = datetime.fromisoformat(date_str)
        days = (datetime.now() - post_date).days
        if days == 0:
            return "сегодня"
        return f"{days} дн. назад"
    except:
        return "дата неизвестна"

def linkify_address(text: str) -> str:
    if not text:
        return "Адрес не указан"
    encoded = quote(text)
    return f"<a href='https://yandex.ru/maps/?text={encoded}'>{text}</a>"

def detect_urgency(text: str) -> str:
    text = text.lower()
    if "срочн" in text:
        return "🔥 Срочно"
    elif any(kw in text for kw in ["не срочн", "можно позже"]):
        return "⏱ Не срочно"
    return "❔ Не указано"

def extract_contacts(text: str) -> str:
    phones = re.findall(r"(?:\+7|8)\d{10}", text)
    links = re.findall(r"https?://\S+", text)
    handles = re.findall(r"(?:@|t\.me/)\w+", text)
    combined = phones + handles + links
    return "\n".join(combined[:3]) if combined else "Контакты не найдены"

# Удалена старая extract_address, используем импортированную из vk_parser

def extract_needs(text: str) -> str:
    patterns = [
        r"(?<=нужн[оаи]|ищем|требуетс[яи]|необходим[оа]|примем|собираем|сбор)[^.!?;\n]*",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            sentence = match.group(0).strip(" :,-")
            return sentence.capitalize() + "..." if sentence else "Нужна помощь"
    return "Нужна помощь (детали в посте)"

# Команды
@dp.message(Command("start"))
async def start_handler(message: Message):
    keyboard = [
        [KeyboardButton(text=city)] for city in CITIES
    ]
    keyboard.append([KeyboardButton(text="🌆 Другой город")])
    
    await message.answer(
        "🐾 Привет! Выберите город для поиска приютов:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
            input_field_placeholder="Выберите или введите город"
        )
    )

# Остальные команды остаются без изменений...

async def show_shelters(message: Message, city: str):
    shelters = get_shelters_for_city(city)
    
    if not shelters:
        await message.answer(f"🔍 Ищем приюты в {city}...")
        try:
            from vk_parser import search_vk_groups
            await asyncio.to_thread(search_vk_groups, city)
            shelters = get_shelters_for_city(city)
        except Exception as e:
            await message.answer("⚠️ Ошибка поиска, попробуйте позже")
            print(f"Error: {e}")
            return

    buttons = [
        [InlineKeyboardButton(
            text=f"{name[:20]}... {days_ago(post_date)}",
            callback_data=f"info_{shelter_id}"
        )] for shelter in shelters
        for shelter_id, name, _, _, _, post_date in [shelter]
    ]
    
    await message.answer(
        f"🏠 Найдено приютов в {city}: {len(shelters)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(lambda c: c.data.startswith("info_"))
async def show_info(callback: types.CallbackQuery):
    shelter_id = callback.data[5:]
    shelter = get_shelter_by_id(shelter_id)
    if not shelter:
        await callback.message.answer("Информация устарела")
        return

    name, link, info, post_date = shelter
    address = extract_address(info or "")[:50]  # Используем новый парсер
    needs = extract_needs(info or "")
    
    msg = (
        f"<b>{name}</b>\n"
        f"⏳ {days_ago(post_date)}\n"
        f"📍 {linkify_address(address)}\n"
        f"📞 {extract_contacts(info or '')}\n\n"
        f"<i>{needs}</i>\n"
        f"<a href='{link}'>🔗 Оригинальный пост</a>"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💾 Сохранить", callback_data=f"fav|{shelter_id}|{link}"),
        InlineKeyboardButton(text="🗺 Карта", url=f"https://yandex.ru/maps/?text={quote(address)}")
    ]])

    # Управление историей сообщений
    user_id = callback.from_user.id
    try:
        if user_id in user_last_msg:
            await callback.message.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=user_last_msg[user_id]
            )
    except:
        pass
    
    sent = await callback.message.answer(
        msg, 
        reply_markup=markup, 
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    user_last_msg[user_id] = sent.message_id
    await callback.answer()

# Остальные обработчики без изменений...

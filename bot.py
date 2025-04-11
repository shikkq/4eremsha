from aiogram import Dispatcher, types, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from database import (
    init_db, get_shelters_for_city, add_favorite,
    get_user_favorites, get_recent_posts_for_group,
    get_shelter_by_id, get_filtered_shelters
)
import asyncio
import re

# Инициализация базы данных (если база уже существует — данные не удаляются)
init_db()
dp = Dispatcher()

# Основной список предлагаемых городов
CITIES = ["Новосибирск"]
# Словарь для сохранения выбранного пользователем города: user_id -> city
user_city: dict[int, str] = {}
# Словарь для отслеживания последнего сообщения с информацией по приюту:
# user_id -> message_id, чтобы удалять прошлое сообщение при выборе нового приюта
user_last_msg: dict[int, int] = {}

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "Привет! Выберите город, чтобы найти приюты, которым нужна помощь:",
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
        "👋 Я бот, помогающий волонтёрам находить приюты и посты с нуждами.\n\n"
        "📌 /start — начать работу, выбрать город\n"
        "⭐ /favorites — ваши избранные посты\n"
        "ℹ️ /about — узнать о проекте\n"
        "❓ /help — список команд"
    )

@dp.message(Command("about"))
async def about_handler(message: Message):
    await message.answer(
        "🐾 Этот бот — часть школьного социального проекта. Он помогает волонтёрам находить приюты, "
        "которым нужна помощь, и отслеживать актуальные посты. Парсинг осуществляется с ВКонтакте.\n\n"
        "Проект некоммерческий 💙"
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
    # Получаем приюты из базы для указанного города
    shelters = get_shelters_for_city(city)

    if not shelters:
        await message.answer(f"📭 Информации по городу {city} пока нет. Ищем свежие данные...")
        try:
            from vk_parser import search_vk_groups
            await asyncio.to_thread(search_vk_groups, city)
        except Exception as e:
            await message.answer("⚠️ Произошла ошибка при попытке собрать информацию.")
            print("Ошибка парсинга:", e)

        # Повторяем проверку каждые 2 секунды (до 10 секунд)
        for _ in range(5):
            await asyncio.sleep(2)
            shelters = get_shelters_for_city(city)
            if shelters:
                break

        if not shelters:
            await message.answer("Пока нет актуальной информации. Попробуйте позже.")
            return

    # Формируем список inline-кнопок для найденных приютов
    buttons = []
    for shelter in shelters:
        # Извлекаем id, name, url, info, дату поста (остальные поля)
        shelter_id, name, url, _, info, post_date = shelter
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"info_{shelter_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer("📋 Вот список найденных приютов:", reply_markup=keyboard)

    # Дополнительные кнопки фильтрации по типу нужды
    filter_buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔧 Волонтёрство", callback_data="filter_volunteer"),
                InlineKeyboardButton(text="📦 Сбор", callback_data="filter_collection")
            ]
        ]
    )
    await message.answer("Вы также можете отфильтровать по типу нужды:", reply_markup=filter_buttons)

def trim_to_sentence(text: str, limit: int = 4096) -> str:
    """
    Если текст превышает лимит, обрезает его до конца последнего полного предложения или абзаца.
    """
    if len(text) <= limit:
        return text
    cutoff = text[:limit]
    last_dot = cutoff.rfind(". ")
    last_newline = cutoff.rfind("\n")
    cut_pos = max(last_dot, last_newline)
    return (cutoff[:cut_pos+1] if cut_pos > 0 else cutoff.rstrip()) + "..."

@dp.callback_query(lambda c: c.data.startswith("info_"))
async def show_info(callback: types.CallbackQuery):
    shelter_id = callback.data[5:]
    row = get_shelter_by_id(shelter_id)
    if row:
        name, link, info, post_date = row
        msg = f"<b>{name}</b>\n{link}\n"
        if post_date:
            msg += f"\n🗓 Дата поста: {post_date}\n"
        msg += f"\n{trim_to_sentence(info or 'Нет описания.')}"
        button_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⭐ В избранное", callback_data=f"fav|{shelter_id}|{link}")]
            ]
        )
        # Удаляем предыдущую информацию, если таковая уже была отправлена пользователю
        user_id = callback.from_user.id
        if user_id in user_last_msg:
            try:
                await callback.message.bot.delete_message(callback.message.chat.id, user_last_msg[user_id])
            except Exception as e:
                print(f"Ошибка удаления предыдущего сообщения: {e}")
        sent_msg = await callback.message.answer(msg, reply_markup=button_markup, parse_mode="HTML")
        user_last_msg[user_id] = sent_msg.message_id
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
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton("🆕 Свежие посты приюта", callback_data=f"recent_posts_{group_id}")]]
    )

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
            msg = f"{trim_to_sentence(text)}\n\n🔗 {url}"
            await callback_query.message.answer(msg)
    else:
        await callback_query.message.answer("Нет свежих постов за последние 7 дней 😿")
    await callback_query.answer()

@dp.callback_query(F.data.in_({"filter_volunteer", "filter_collection"}))
async def handle_filter(callback: types.CallbackQuery):
    city = user_city.get(callback.from_user.id)
    if not city:
        await callback.message.answer("Сначала выберите или введите город.")
        return
    filter_type = "Волонтёрство" if callback.data == "filter_volunteer" else "Сбор"
    filtered = get_filtered_shelters(city, filter_type)
    if not filtered:
        await callback.message.answer("Пока нет записей по данному фильтру.")
        await callback.answer()
        return
    buttons = []
    for shelter_id, name in filtered[:10]:
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"info_{shelter_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("Вот, что удалось найти по фильтру:", reply_markup=keyboard)
    await callback.answer()

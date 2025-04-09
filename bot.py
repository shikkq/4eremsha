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
import asyncio

init_db()
dp = Dispatcher()
CITIES = ["Новосибирск"]
user_city: dict[int, str] = {}

@dp.message(Command("start"))
async def start_handler(message: Message):
    shelters = get_shelters_for_city("Новосибирск")  # предположим, что ты заранее получаешь приюты по дефолтному городу

    if not shelters:
        await message.answer(
            "⚠️ В этом городе пока нет подходящих приютов. Попробуем найти свежую информацию позже.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Другой город")]
                ],
                resize_keyboard=True
            )
        )
        return

    buttons = [[KeyboardButton(text=city)] for city in CITIES]
    buttons.append([KeyboardButton(text="Другой город")])
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Привет! Выберите город, чтобы найти приюты, которым нужна помощь:", reply_markup=keyboard)

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer("👋 Я бот, помогающий волонтёрам находить приюты и посты с нуждами.\n\n"
                         "📌 /start — выбрать город\n"
                         "⭐ /favorites — ваши избранные посты\n"
                         "ℹ️ /about — узнать о проекте\n"
                         "❓ /help — список команд")

@dp.message(Command("about"))
async def about_handler(message: Message):
    await message.answer("🐾 Этот бот — часть школьного социального проекта. Он помогает волонтёрам находить приюты, "
                         "которым нужна помощь, и отслеживать актуальные посты. Парсинг осуществляется с ВКонтакте.\n\n"
                         "Проект некоммерческий 💙")

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
        await message.answer("🔍 Приюты не найдены. Пробуем найти свежую информацию...")
        try:
            from vk_parser import search_vk_groups
            await asyncio.to_thread(search_vk_groups, city)
            await asyncio.sleep(2)
        except Exception as e:
            await message.answer("⚠️ Произошла ошибка при попытке найти приюты.")
            print("Ошибка парсинга:", e)

        shelters = get_shelters_for_city(city)

        if not shelters:
            await message.answer("К сожалению, приютов не найдено.")
            return

    keyboard = InlineKeyboardMarkup()
    for shelter in shelters:
        shelter_id, name, url, _, info = shelter
        keyboard.add(InlineKeyboardButton(text=name, callback_data=f"info_{shelter_id}"))

    await message.answer("📋 Вот список найденных приютов:", reply_markup=keyboard)

    # Добавим фильтры
    filter_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 Волонтёрство", callback_data="filter_volunteer"),
            InlineKeyboardButton(text="📦 Сбор", callback_data="filter_collection"),
        ]
    ])
    await message.answer("Вы также можете отфильтровать по типу нужды:", reply_markup=filter_buttons)

@dp.callback_query(lambda c: c.data.startswith("info_"))
async def show_info(callback: types.CallbackQuery):
    shelter_id = callback.data[5:]
    from database import get_shelter_by_id
    row = get_shelter_by_id(shelter_id)
    if row:
        name, link, info = row
        msg = f"<b>{name}</b>\n{link}\n\n{info or 'Нет описания.'}"
        msg = msg[:4093] + "..." if len(msg) > 4096 else msg
        button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ В избранное", callback_data=f"fav|{shelter_id}|{link}")]
        ])
        await callback.message.answer(msg, reply_markup=button, parse_mode="HTML")
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
            msg = msg[:4093] + "..." if len(msg) > 4096 else msg
            await callback_query.message.answer(msg)
    else:
        await callback_query.message.answer("Нет свежих постов за последние 7 дней 😿")
    await callback_query.answer()

@dp.callback_query(F.data.in_({"filter_volunteer", "filter_collection"}))
async def handle_filter(callback: types.CallbackQuery):
    from database import get_filtered_shelters
    city = user_city.get(callback.from_user.id)
    if not city:
        await callback.message.answer("Сначала выберите или введите город.")
        return
    filter_type = "Волонтёрство" if callback.data == "filter_volunteer" else "Сбор"
    filtered = get_filtered_shelters(city, f"📦 {filter_type}" if "Сбор" in filter_type else f"🔧 {filter_type}")
    if not filtered:
        await callback.message.answer("По этому фильтру ничего не найдено.")
        return
    keyboard = InlineKeyboardMarkup()
    for shelter_id, name in filtered[:10]:
        keyboard.add(InlineKeyboardButton(text=name, callback_data=f"info_{shelter_id}"))
    await callback.message.answer("Вот, что удалось найти по фильтру:", reply_markup=keyboard)
    await callback.answer()

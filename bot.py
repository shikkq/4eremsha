from aiogram import Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import (
    init_db, get_shelters_for_city, add_favorite,
    get_user_favorites, get_recent_posts_for_group,
    get_shelter_by_id, get_filtered_shelters
)
import asyncio
import re
from datetime import datetime
from urllib.parse import quote

# Инициализация базы данных (если база уже существует — данные не удаляются)
init_db()
dp = Dispatcher()

# Список предлагаемых городов (отображаются через inline-кнопки)
CITIES = ["Новосибирск"]
# Словарь для сохранения выбранного пользователем города: user_id -> city
user_city: dict[int, str] = {}
# Словарь для отслеживания последнего редактируемого сообщения для каждого пользователя,
# чтобы обновлять его (и не засорять чат)
user_last_msg: dict[int, types.Message] = {}

def build_city_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=city, callback_data=f"city_{city}")] for city in CITIES]
    buttons.append([InlineKeyboardButton(text="Другой город", callback_data="city_custom")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def update_message(msg_obj, text: str, reply_markup: InlineKeyboardMarkup = None) -> types.Message:
    """
    Если возможно, редактирует переданное сообщение, иначе отправляет новое.
    """
    try:
        await msg_obj.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        return msg_obj
    except Exception:
        new_msg = await msg_obj.answer(text, reply_markup=reply_markup, parse_mode="HTML")
        return new_msg

@dp.message(Command("start"))
async def start_handler(message: Message):
    sent = await message.answer(
        "Привет! Выберите город, чтобы найти приюты, которым нужна помощь:",
        reply_markup=build_city_keyboard()
    )
    user_last_msg[message.from_user.id] = sent

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "👋 Я бот, помогающий волонтёрам находить приюты и посты с нуждами.\n\n"
        "📌 /start — начать работу, выбрать город\n"
        "⭐ /fav — ваши сохранённые посты\n"
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

# Обработка inline нажатий для выбора города
@dp.callback_query(lambda c: c.data.startswith("city_"))
async def process_city(callback: types.CallbackQuery):
    # callback.data = "city_{city}" (например, "city_Новосибирск")
    city = callback.data[5:]
    user_city[callback.from_user.id] = city
    msg = await update_message(callback.message, f"Ищем приюты в городе {city}, подождите немного...")
    user_last_msg[callback.from_user.id] = msg
    await show_shelters(msg, city)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "city_custom")
async def choose_custom_city(callback: types.CallbackQuery):
    # Просим ввести город вручную
    msg = await update_message(callback.message, "Введите название города вручную:")
    user_last_msg[callback.from_user.id] = msg
    await callback.answer()

# Обработка текстового ввода при выборе другого города
@dp.message(lambda m: m.text and m.from_user.id not in user_city or (m.text not in CITIES))
async def handle_custom_city(message: Message):
    # Если пользователь ранее нажал "Другой город", то принимаем ввод
    city = message.text.strip()
    user_city[message.from_user.id] = city
    sent = await message.answer(f"Ищем приюты в городе {city}, подождите немного...")
    user_last_msg[message.from_user.id] = sent
    await show_shelters(sent, city)

async def show_shelters(msg_obj, city: str):
    # Получаем приюты для указанного города
    shelters = get_shelters_for_city(city)

    if not shelters:
        temp = await update_message(msg_obj, f"📭 Информации по городу {city} пока нет. Ищем свежие данные...")
        user_last_msg[msg_obj.chat.id] = temp
        try:
            from vk_parser import search_vk_groups
            await asyncio.to_thread(search_vk_groups, city)
        except Exception as e:
            await msg_obj.answer("⚠️ Произошла ошибка при попытке собрать информацию.")
            print("Ошибка парсинга:", e)

        # Повторяем проверку каждые 2 секунды (до 10 секунд)
        for _ in range(5):
            await asyncio.sleep(2)
            shelters = get_shelters_for_city(city)
            if shelters:
                break

        if not shelters:
            await update_message(msg_obj, "Пока нет актуальной информации. Попробуйте позже.")
            return

    # Формируем inline-кнопки для найденных приютов
    buttons = []
    for shelter in shelters:
        # Извлекаем: id, name, url, _, info, post_date
        shelter_id, name, url, _, info, post_date = shelter
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"info_{shelter_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Добавляем кнопку "Вернуться к городам"
    keyboard.add(InlineKeyboardButton(text="🌆 Вернуться к городам", callback_data="back_cities"))
    msg = await update_message(msg_obj, "📋 Вот список найденных приютов:", reply_markup=keyboard)
    user_last_msg[msg.chat.id] = msg

def trim_to_sentence(text: str, limit: int = 4096) -> str:
    """
    Обрезает текст, не разрывая слово, если превышает лимит.
    """
    if len(text) <= limit:
        return text
    cutoff = text[:limit]
    if " " in cutoff:
        cutoff = cutoff[:cutoff.rfind(" ")]
    return cutoff + "..."

def clean_info(info: str) -> tuple[str, str]:
    """
    Обрабатывает исходный текст описания:
    - Определяет срочность: ищет ключевые слова «срочно» / «не срочно».
    - Удаляет слова "волонтёрство" и "сбор".
    - Убирает повторы.
    - Если встречается раздел "что нужно:", то берётся первое предложение после него,
      что трактуется как основная потребность.
    Возвращает кортеж: (основная потребность, срочность)
    """
    # Определяем срочность
    urgency = "Не указано"
    lower_info = info.lower()
    if "срочно" in lower_info:
        urgency = "Срочно"
    elif "не срочно" in lower_info:
        urgency = "Не срочно"

    # Удаляем нежелательные слова
    for word in ["волонтёрство", "сбор"]:
        info = info.replace(word, "")

    # Убираем дублирующие строки
    lines = [line.strip() for line in info.split("\n") if line.strip()]
    seen = set()
    unique_lines = []
    for line in lines:
        if line.lower() not in seen:
            unique_lines.append(line)
            seen.add(line.lower())
    cleaned_info = "\n".join(unique_lines)

    # Если встречается блок «что нужно:», берём первое предложение после него
    lower_clean = cleaned_info.lower()
    if "что нужно:" in lower_clean:
        idx = lower_clean.index("что нужно:") + len("что нужно:")
        remainder = cleaned_info[idx:].strip()
        # Берём первое предложение (до точки или переноса строки)
        sentence = re.split(r"[.!?]", remainder)[0].strip()
        main_need = sentence
    else:
        # Если не найдено, используем первые 100 символов как базовую потребность
        main_need = cleaned_info[:100].strip()

    return main_need, urgency

@dp.callback_query(lambda c: c.data.startswith("info_"))
async def show_info(callback: types.CallbackQuery):
    shelter_id = callback.data[5:]
    row = get_shelter_by_id(shelter_id)
    if row:
        name, link, info, post_date = row

        # Формируем кликабельный адрес через Google Maps
        link_encoded = quote(link)
        link_url = f"https://www.google.com/maps/search/{link_encoded}"
        link_html = f'<a href="{link_url}">{link}</a>'

        msg_text = f"<b>{name}</b>\n{link_html}\n"

        # Вычисляем, сколько дней назад был пост
        if post_date:
            try:
                dt = datetime.strptime(post_date, "%Y-%m-%d")
            except Exception:
                try:
                    dt = datetime.strptime(post_date, "%d.%m.%Y")
                except Exception:
                    dt = None
            if dt:
                days_ago = (datetime.now() - dt).days
                msg_text += f"\n🗓 {days_ago} дней назад\n"

        # Обработка и структурирование блока потребности
        if info:
            main_need, urgency = clean_info(info)
        else:
            main_need, urgency = "Нет описания.", "Не указано"
        msg_text += f"\n<b>Основная потребность:</b>\n{trim_to_sentence(main_need, 400)}\n"
        msg_text += f"\n<b>Срочность:</b> {urgency}"

        # Формируем дополнительную навигационную клавиатуру:
        # кнопка сохранения, вернуться к приютам (для текущего города), вернуться к городам, сохранённые посты
        city = user_city.get(callback.from_user.id, "")
        nav_buttons = [
            [InlineKeyboardButton(text="💾 Сохранить", callback_data=f"fav|{shelter_id}|{link}")],
            [InlineKeyboardButton(text="🏠 Вернуться к приютам", callback_data=f"back_shelters|{city}")],
            [InlineKeyboardButton(text="🌆 Вернуться к городам", callback_data="back_cities")],
            [InlineKeyboardButton(text="⭐ Сохранённые посты", callback_data="fav_menu")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=nav_buttons)

        # Редактируем сообщение, заменяя старую информацию новой
        edited_msg = await update_message(callback.message, msg_text, reply_markup=keyboard)
        user_last_msg[callback.from_user.id] = edited_msg
    else:
        await callback.message.answer("Не удалось найти информацию.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("fav|"))
async def add_to_favorites(callback: types.CallbackQuery):
    # callback.data = "fav|{group_id}|{post_url}"
    _, group_id, post_url = callback.data.split("|")
    user_id = callback.from_user.id
    add_favorite(user_id, post_url, group_id)
    await callback.answer("Добавлено в сохранённые! 💾")

@dp.callback_query(lambda c: c.data == "back_cities")
async def back_to_cities(callback: types.CallbackQuery):
    msg = await update_message(callback.message, "Привет! Выберите город, чтобы найти приюты, которым нужна помощь:", reply_markup=build_city_keyboard())
    user_last_msg[callback.from_user.id] = msg
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("back_shelters"))
async def back_to_shelters(callback: types.CallbackQuery):
    # callback.data = "back_shelters|{city}"
    parts = callback.data.split("|", 1)
    if len(parts) < 2:
        await callback.answer("Ошибка: город не указан.")
        return
    city = parts[1]
    msg = await update_message(callback.message, f"Ищем приюты в городе {city}, подождите немного...")
    user_last_msg[callback.from_user.id] = msg
    await show_shelters(msg, city)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "fav_menu")
async def show_fav_menu(callback: types.CallbackQuery):
    # Просто перенаправляем на команду /fav (показываем сохранённые посты)
    # Можно вызвать show_favorites, но здесь редактируем сообщение
    user_id = callback.from_user.id
    favorites = get_user_favorites(user_id)
    if not favorites:
        text = "У вас нет сохранённых постов."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌆 Вернуться к городам", callback_data="back_cities")]
        ])
        msg = await update_message(callback.message, text, reply_markup=kb)
        user_last_msg[user_id] = msg
    else:
        text = "⭐ Сохранённые посты:\n"
        kb_buttons = []
        for post_url, group_id in favorites:
            kb_buttons.append([InlineKeyboardButton(text="🔗 Пост", url=post_url)])
        kb_buttons.append([InlineKeyboardButton(text="🌆 Вернуться к городам", callback_data="back_cities")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
        msg = await update_message(callback.message, text, reply_markup=kb)
        user_last_msg[user_id] = msg
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("recent_posts_"))
async def handle_recent_posts(callback: types.CallbackQuery):
    group_id = callback.data.replace("recent_posts_", "")
    posts = get_recent_posts_for_group(group_id)
    if posts:
        text = ""
        for url, text_part in posts:
            text += f"{trim_to_sentence(text_part, 300)}\n\n🔗 {url}\n\n"
        await update_message(callback.message, text)
    else:
        await update_message(callback.message, "Нет свежих постов за последние 7 дней 😿")
    await callback.answer()

@dp.message(Command("fav"))
async def show_favorites(message: Message):
    user_id = message.from_user.id
    favorites = get_user_favorites(user_id)
    if not favorites:
        await message.answer("У вас нет сохранённых постов.")
        return
    text = "⭐ Сохранённые посты:\n"
    kb_buttons = []
    for post_url, group_id in favorites:
        kb_buttons.append([InlineKeyboardButton(text="🔗 Пост", url=post_url)])
    kb_buttons.append([InlineKeyboardButton(text="🌆 Вернуться к городам", callback_data="back_cities")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    sent = await message.answer(text, reply_markup=keyboard)
    user_last_msg[user_id] = sent

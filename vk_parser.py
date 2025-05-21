import requests
import time
import re
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import add_shelter
from urllib.parse import quote_plus

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_KEYWORDS = os.getenv("VK_KEYWORDS", "приют,волонт,животн,кошк,собак,хвост,помощь,нужн,срочно,помогите,поддержка").split(",")
VK_API_VERSION = "5.199"
CACHE_FILE = "parsed_groups.json"

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        parsed_groups = set(json.load(f))
else:
    parsed_groups = set()

def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(parsed_groups), f)

def get_city_id(city_name):
    url = "https://api.vk.com/method/database.getCities"
    params = {
        "access_token": VK_TOKEN,
        "country_id": 1,
        "q": city_name,
        "count": 1,
        "v": VK_API_VERSION
    }
    res = requests.get(url, params=params).json()
    items = res.get("response", {}).get("items", [])
    return items[0]["id"] if items else None

def contains_keywords(text):
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in VK_KEYWORDS)

def contains_city(text, city_name):
    lowered = text.lower()
    city_lower = city_name.lower()
    if f"г. {city_lower}" in lowered:
        return True
    if re.search(rf"\b{re.escape(city_lower)}\b", lowered):
        return True
    return False

def normalize_contacts(contacts):
    cleaned = set()
    for contact in contacts:
        # Удаляем все нецифровые символы, кроме + для номеров
        normalized = re.sub(r"[^\d+]", "", contact)
        if len(normalized) == 11 and normalized.startswith("8"):
            normalized = "+7" + normalized[1:]
        cleaned.add(normalized)
    return cleaned

def extract_info_from_posts(posts_texts, city_name):
    """
    Обрабатывает список постов и возвращает лучший вариант информации, 
    содержащий дату поста, блок "Что нужно:", контакты и адрес, если они найдены.
    Если релевантность (score) меньше порогового значения, возвращается None.
    """
    keyword_found = False
    best_info = None
    best_score = 0

    help_keywords = ["нужны", "нужен", "нужная", "нужное", "помощь", "помогите", "срочно", "сбор", "поддержка"]
    contact_patterns = [
        r"\+7[\d\-\s]{10,15}",
        r"\b8[\d\-\s]{9,15}",
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        r"https?://[^\s]+"
    ]
    address_keywords = ["ул.", "улица", "проспект", "бульвар", "переулок", "по адресу", "двор", "место встречи", "адрес"]

    for post in posts_texts:
        text = post.get("text", "")
        lowered = text.lower()

        if not contains_keywords(text):
            continue

        if city_name and not contains_city(text, city_name):
            continue

        keyword_found = True
        score = 0
        contacts = set()
        addresses = set()
        info_lines = []

        post_date_unix = post.get("date")
        post_date = datetime.fromtimestamp(post_date_unix)
        last_date = post_date.strftime("%d.%m.%Y") if post_date_unix else "неизвестно"

        # Проверка на неактивность
        fourteen_days_ago = datetime.now() - timedelta(days=14)
        post_date = datetime.fromtimestamp(post_date_unix)
        is_inactive = post_date < fourteen_days_ago
        if is_inactive:
            score -= 3
        contacts = normalize_contacts(contacts)

        if any(kw in lowered for kw in address_keywords):
            snippet = text[:300]
            if 10 < len(snippet) < 300:
                addresses.add(snippet)
                score += 2

        if any(kw in lowered for kw in ["приют", "животн", "собак", "кошк", "хвост", "волонт"]):
            score += 1
        if city_name and contains_city(text, city_name):
            score += 1

        # Формирование итогового результата
        if score >= best_score:
            best_score = score
            result = f"\U0001F4C5 Дата поста: {last_date}\n\n"
            if info_lines:
                result += "\U0001F4CC Что нужно:\n" + "\n".join(info_lines[:2]) + "\n"
            if contacts:
                result += "\n\U0001F4DE Контакты:\n" + "\n".join(contacts) + "\n"
            if addresses:
                result += "\n\U0001F4CD Адрес или место:\n" + "\n".join(addresses) + "\n"

            # Убираем вывод ключевых слов в контексте согласно ТЗ

            if not contacts or not addresses:
                result += "\n⚠️ Пост может быть неполным — проверьте информацию вручную.\n"

            best_info = result.strip()

    if not keyword_found:
        print("❌ В постах нет ключевых слов — пропускаем.")
        return None
    if best_score < 5:
        print(f"⚠️ Недостаточно баллов (score={best_score}) — пропускаем.")
        return None

    return best_info

def get_group_posts(group_id):
    url = "https://api.vk.com/method/wall.get"
    params = {
        "access_token": VK_TOKEN,
        "owner_id": -group_id,
        "count": 10,
        "filter": "owner",
        "v": VK_API_VERSION
    }
    try:
        res = requests.get(url, params=params).json()
        posts = res.get("response", {}).get("items", [])
        result = []
        fourteen_days_ago = datetime.now() - timedelta(days=14)

        for post in posts:
            date_unix = post.get("date")
            text = post.get("text", "")
            post_id = post.get("id")
            if date_unix and text and len(text) > 50:
                post_date = datetime.fromtimestamp(date_unix)
                if post_date > fourteen_days_ago:
                    result.append({"id": post_id, "date": date_unix, "text": text})

        if not result and posts:
            latest_post = posts[0]
            return [{
                "id": latest_post.get("id"),
                "date": latest_post.get("date"),
                "text": f"(неактивно)\n{latest_post.get('text', '')[:400]}"
            }]

        return result

    except Exception as e:
        print(f"⚠️ Ошибка при получении постов группы {group_id}: {e}")
        return []


def search_vk_groups(city_name):
    start = time.time()
    print(f"\n🔍 [VK] Начинаю парсинг города: {city_name}")

    city_id = get_city_id(city_name)
    if not city_id:
        print(f"❌ Город '{city_name}' не найден.")
        return

    total_processed = 0
    total_groups_checked = 0

    exclusion_keywords = [
        # ... (список исключений без изменений)
    ]

    # Улучшенная обработка ключевых слов
    VK_KEYWORDS = [kw.strip() for kw in VK_KEYWORDS]

    for keyword in VK_KEYWORDS:
        offset = 0
        while total_processed < 10:
            # Экранируем город для поиска
            encoded_city = quote_plus(city_name)
            url = "https://api.vk.com/method/groups.search"
            params = {
                "access_token": VK_TOKEN,
                "q": f"{keyword} {encoded_city}",
                "count": 20,
                "sort": 0,
                "offset": offset,
                "city_id": city_id,
                "v": VK_API_VERSION
            }
            try:
                res = requests.get(url, params=params).json()
                if 'error' in res:
                    print(f"❌ Ошибка API: {res['error']['error_msg']}")
                    break
                groups = res.get("response", {}).get("items", [])
            except Exception as e:
                print(f"⚠️ Ошибка при запросе: {e}")
                break

            if not groups:
                break

            for group in groups:
                # ... (проверки группы без изменений до условия parsed_groups)

                # Ослабляем проверку названия группы
                if any(x in lowered_name for x in exclusion_keywords):
                    print(f"⛔ Группа '{group_name}' — не по теме — пропускаем.")
                    continue

                # Переносим часть проверок в анализ постов
                print(f"🔹 Проверяем группу: {group_name}")
                group_link = f"https://vk.com/{group['screen_name']}"
                post_texts = get_group_posts(group_id)
                time.sleep(0.34)

                if not post_texts:
                    print("⚠️ Нет постов — пропускаем.")
                    continue

                # Добавляем проверку даты последнего поста
                latest_post_date = datetime.fromtimestamp(post_texts[0]['date'])
                if (datetime.now() - latest_post_date).days > 60:
                    print(f"⚠️ Группа неактивна (последний пост {latest_post_date.date()}) — пропускаем.")
                    continue

                info = extract_info_from_posts(post_texts, city_name)
                # ... (остальная обработка без изменений)

    # ... (сохранение кэша и вывод статистики)

    print(f"✅ [VK] Город {city_name} обработан за {time.time() - start:.2f} сек")
    print(f"🔍 Всего проверено групп: {total_groups_checked}")

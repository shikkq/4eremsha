import requests
import time
import re
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import add_shelter

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_KEYWORDS = os.getenv("VK_KEYWORDS", "").split(",")
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

def extract_info_from_posts(posts_texts):
    info_lines = []
    contacts = set()
    addresses = set()
    last_date = None
    score = 0

    for post in posts_texts:
        text = post.get("text") if isinstance(post, dict) else post
        if not isinstance(text, str):
            continue

        lowered = text.lower()
        post_date_unix = post.get("date")
        if post_date_unix:
            last_date = datetime.fromtimestamp(post_date_unix).strftime("%d.%m.%Y")

        # Нужды
        if any(kw in lowered for kw in ["нужны", "срочно", "сбор", "помочь", "волонтёры", "приходите", "ждём"]):
            info_lines.append(text[:400])
            score += 3

        # Контакты
        phones = re.findall(r"\+7[\d\- ]{10,15}|\b8[\d\- ]{9,15}", text)
        emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        urls = re.findall(r"https?://[^\s]+", text)
        if phones or emails or urls:
            contacts.update(phones + emails + urls)
            score += 2

        # Адрес
        if any(kw in lowered for kw in ["ул.", "улица", "проспект", "по адресу", "двор", "встреча в", "место встречи"]):
            addresses.add(text[:300])
            score += 2

        # Общие ключевые слова
        if any(kw in lowered for kw in ["приют", "животн", "собак", "кошк", "хвост", "волонт"]):
            score += 1

    if score < 5:
        print(f"   ⚠️ Слишком низкий рейтинг постов: {score}/10, пропускаем.")
        return None

    result = ""
    if last_date:
        result += f"🗓 Дата поста: {last_date}\n\n"

    if info_lines:
        result += "📌 Что нужно:\n" + "\n".join(info_lines[:3]) + "\n"
    if contacts:
        result += "\n📞 Контакты:\n" + "\n".join(contacts) + "\n"
    if addresses:
        result += "\n📍 Адрес или место:\n" + "\n".join(addresses) + "\n"

    # Предупреждение, если нет адреса или контактов
    if not contacts or not addresses:
        result += "\n⚠️ Пост может быть неполным — проверьте информацию вручную.\n"

    return result.strip()

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

    for keyword in VK_KEYWORDS:
        url = "https://api.vk.com/method/groups.search"
        params = {
            "access_token": VK_TOKEN,
            "q": f"{keyword} {city_name}",
            "count": 20,
            "sort": 0,
            "city_id": city_id,
            "v": VK_API_VERSION
        }
        res = requests.get(url, params=params).json()
        groups = res.get("response", {}).get("items", [])

        for group in groups:
            if group["is_closed"] == 0:
                group_id = group["id"]
                group_key = f"vk_{group_id}"
                group_name = group["name"]
                group_link = f"https://vk.com/{group['screen_name']}"

                # Исключаем неподходящие группы по ключевым словам
                lowered_name = group_name.lower()
                if not any(kw in lowered_name for kw in ["приют", "волонт", "животн", "кошк", "собак", "хвост"]):
                    continue

                print(f"   🔹 {group_name}")

                post_texts = get_group_posts(group_id)
                if not post_texts:
                    print("   ⚠️ Нет подходящих постов, пропускаем.")
                    continue

                info = extract_info_from_posts(post_texts)
                if not info:
                    print("   ⚠️ Посты без нужной информации, пропускаем.")
                    continue

                add_shelter(group_key, group_name, group_link, city_name, info)

                if group_key not in parsed_groups:
                    parsed_groups.add(group_key)
                    save_cache()

                total_processed += 1
                print(f"   ✅ Добавлен [{total_processed}/10]")

                if total_processed >= 10:
                    print("📦 Достигнут лимит в 10 групп.")
                    break

    print(f"✅ [VK] Город {city_name} обработан за {time.time() - start:.2f} сек")

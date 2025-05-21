
import requests
import re
import time
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_KEYWORDS = os.getenv("VK_KEYWORDS", "приют,животные,кошки,собаки").split(",")
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

def get_group_info(group_id):
    url = "https://api.vk.com/method/groups.getById"
    params = {
        "access_token": VK_TOKEN,
        "group_id": group_id,
        "fields": "description,city",
        "v": VK_API_VERSION
    }
    try:
        res = requests.get(url, params=params).json()
        return res.get('response', [{}])[0]
    except Exception as e:
        print(f"[Ошибка] Получение информации о группе {group_id}: {e}")
        return {}

def is_city_match(group_info, target_city):
    target_lower = target_city.lower()
    description = group_info.get('description', '').lower()

    if 'city' in group_info:
        group_city = group_info['city']['title'].lower()
        if target_lower in group_city:
            print(f"[Город] Найдено совпадение по полю city: {group_city}")
            return True

    patterns = [
        rf"\b{re.escape(target_lower)}\b",
        rf"\bг\.?\s*{re.escape(target_lower)}\b",
        rf"\b{re.escape(target_lower[:5])}\w*\b"
    ]

    if any(re.search(pattern, description) for pattern in patterns):
        print(f"[Город] Найдено совпадение в описании группы")
        return True

    print(f"[Отклонено] Город {target_city} не найден в группе")
    return False

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
        return res.get("response", {}).get("items", [])
    except Exception as e:
        print(f"[Ошибка] Получение постов для группы {group_id}: {e}")
        return []

def extract_post_info(posts):
    relevant_posts = []
    for post in posts:
        text = post.get('text', '')
        if not text.strip():
            print("[Отклонено] Пост без текста")
            continue

        lower_text = text.lower()
        if any(kw.strip() in lower_text for kw in VK_KEYWORDS):
            print(f"[Принят] Пост содержит ключевые слова")
            relevant_posts.append({
                'date': datetime.fromtimestamp(post['date']).strftime("%d.%m.%Y"),
                'text': text[:500]
            })
        else:
            print(f"[Отклонено] Пост не содержит ключевые слова: {text[:100]}...")
    return relevant_posts

def search_vk_groups(city_name):
    print(f"\n🔍 Начинаем поиск для города: {city_name}")
    total_added = 0
    exclusion_keywords = ["бизнес", "магазин", "реклама", "доставка"]

    for keyword in VK_KEYWORDS:
        offset = 0
        while total_added < 10:
            url = "https://api.vk.com/method/groups.search"
            params = {
                "access_token": VK_TOKEN,
                "q": keyword,
                "count": 20,
                "offset": offset,
                "v": VK_API_VERSION
            }

            try:
                response = requests.get(url, params=params).json()
                groups = response.get('response', {}).get('items', [])
                print(f"[{keyword}] Найдено групп: {len(groups)}")

                for group in groups:
                    group_id = abs(group['id'])
                    if group_id in parsed_groups:
                        print(f"[Пропущено] Группа уже обработана: {group['name']}")
                        continue

                    group_info = get_group_info(group_id)
                    time.sleep(0.3)

                    if not is_city_match(group_info, city_name):
                        continue

                    group_name = group['name'].lower()
                    if any(bw in group_name for bw in exclusion_keywords):
                        print(f"[Отклонено] Название содержит стоп-слово: {group_name}")
                        continue

                    posts = get_group_posts(group_id)
                    post_info = extract_post_info(posts)

                    if not post_info:
                        print(f"[Отклонено] Нет подходящих постов в группе {group['name']}")
                        continue

                    # ВСТАВЬ сюда свою функцию сохранения приюта
                    # add_shelter(...)

                    parsed_groups.add(group_id)
                    total_added += 1
                    print(f"[✅ Добавлена] Группа: {group['name']}")

                    if total_added >= 10:
                        break

                offset += 20
                if offset >= 100:
                    break

            except Exception as e:
                print(f"[Ошибка] Обработка keyword='{keyword}': {e}")
                break

    save_cache()
    print(f"🏁 Поиск завершён. Добавлено групп: {total_added}")

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

# Загрузка кэша
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        parsed_groups = set(json.load(f))
else:
    parsed_groups = set()

def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(parsed_groups), f)

def get_group_info(group_id):
    """Получаем расширенную информацию о группе"""
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
        print(f"Ошибка при получении информации о группе: {e}")
        return {}

def is_city_match(group_info, target_city):
    """Проверяем совпадение города в данных группы"""
    target_lower = target_city.lower()
    
    # Проверка официального города группы
    if 'city' in group_info:
        group_city = group_info['city']['title'].lower()
        if target_lower in group_city:
            return True
    
    # Поиск в описании группы
    description = group_info.get('description', '').lower()
    patterns = [
        rf"\b{re.escape(target_lower)}\b",
        rf"\bг\.?\s*{re.escape(target_lower)}\b",
        rf"\b{re.escape(target_lower[:5])}\w*\b"  # Для сокращений типа "Новосиб"
    ]
    
    return any(re.search(pattern, description) for pattern in patterns)

def get_group_posts(group_id):
    """Получаем посты группы (без изменений)"""
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
        print(f"Ошибка при получении постов: {e}")
        return []

def extract_post_info(posts):
    """Анализ постов (убрана проверка города)"""
    relevant_posts = []
    for post in posts:
        text = post.get('text', '')
        if any(kw in text.lower() for kw in VK_KEYWORDS):
            relevant_posts.append({
                'date': datetime.fromtimestamp(post['date']).strftime("%d.%m.%Y"),
                'text': text[:500]
            })
    return relevant_posts

def search_vk_groups(city_name):
    """Основная функция поиска"""
    print(f"\n🔍 Начинаем поиск для города: {city_name}")
    
    total_added = 0
    exclusion_keywords = ["бизнес", "магазин", "реклама", "доставка"]

    for keyword in VK_KEYWORDS:
        offset = 0
        while total_added < 10:
            url = "https://api.vk.com/method/groups.search"
            params = {
                "access_token": VK_TOKEN,
                "q": f"{keyword}",
                "count": 20,
                "offset": offset,
                "v": VK_API_VERSION
            }
            
            try:
                response = requests.get(url, params=params).json()
                groups = response.get('response', {}).get('items', [])
                
                for group in groups:
                    group_id = abs(group['id'])
                    if group_id in parsed_groups:
                        continue
                        
                    # Получаем полную информацию о группе
                    group_info = get_group_info(group_id)
                    time.sleep(0.3)  # Защита от лимита API
                    
                    # Проверка города в описании
                    if not is_city_match(group_info, city_name):
                        continue
                        
                    # Фильтр по названию группы
                    group_name = group['name'].lower()
                    if any(bw in group_name for bw in exclusion_keywords):
                        continue
                        
                    # Анализ постов
                    posts = get_group_posts(group_id)
                    post_info = extract_post_info(posts)
                    
                    if not post_info:
                        continue
                        
                    # Сохранение результатов
                    add_shelter(
                        f"vk_{group_id}",
                        group['name'],
                        f"https://vk.com/{group['screen_name']}",
                        city_name,
                        json.dumps(post_info, ensure_ascii=False)
                    )
                    
                    parsed_groups.add(group_id)
                    total_added += 1
                    print(f"✅ Добавлена группа: {group['name']}")
                    
                    if total_added >= 10:
                        break
                        
                offset += 20
                if offset >= 100:
                    break
                    
            except Exception as e:
                print(f"Ошибка при обработке групп: {e}")
                break

    save_cache()
    print(f"🏁 Поиск завершен. Добавлено групп: {total_added}")

# Пример вызова
search_vk_groups("Новосибирск")

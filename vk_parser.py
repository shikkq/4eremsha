import requests
import re
import time
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_API_VERSION = "5.199"
CACHE_FILE = "parsed_posts.json"

# Настройка ключевых слов и баллов
POSITIVE_KEYWORDS = {
    "приют": 2,
    "животные": 1,
    "кошки": 1,
    "собаки": 1,
    "помощь животным": 3,
    "в поисках дома": 3,
    "спасение животных": 3,
    "бездомные животные": 2,
}
NEGATIVE_KEYWORDS = {
    "бизнес": -2,
    "магазин": -2,
    "реклама": -3,
    "доставка": -2,
    "продажа": -2,
}

MIN_SCORE_THRESHOLD = 2  # Минимальный балл для публикации поста
MAX_POSTS = 10

# Кэшируем обработанные посты по id
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        parsed_posts = set(json.load(f))
else:
    parsed_posts = set()

def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(parsed_posts), f)

def calculate_post_score(text):
    text_lower = text.lower()
    score = 0
    reasons = []

    # Считаем положительные слова
    for phrase, pts in POSITIVE_KEYWORDS.items():
        if phrase in text_lower:
            score += pts
            reasons.append(f"+{pts} '{phrase}'")

    # Считаем отрицательные слова
    for phrase, pts in NEGATIVE_KEYWORDS.items():
        if phrase in text_lower:
            score += pts
            reasons.append(f"{pts} '{phrase}'")

    # Дополнительная логика: если два положительных слова рядом (в одном предложении) + 3 балла
    sentences = re.split(r'[.!?]', text_lower)
    for sentence in sentences:
        found = [kw for kw in POSITIVE_KEYWORDS if kw in sentence]
        if len(found) >= 2:
            score += 3
            reasons.append(f"+3 за связку ключевых слов: {found}")
            break

    return score, reasons

def add_shelter(post_id, group_name, group_url, city_name, post_info_json):
    # Заглушка для функции сохранения в базу или файл
    # TODO: заменить на реальное сохранение
    print(f"Сохраняем пост {post_id} из группы '{group_name}' ({group_url}) для города {city_name}")

def search_vk_groups(city_name):
    print(f"\n🔍 Начинаем поиск постов для города: {city_name}")

    total_added = 0
    offset = 0
    count_per_request = 20

    while total_added < MAX_POSTS:
        url = "https://api.vk.com/method/newsfeed.search"
        params = {
            "access_token": VK_TOKEN,
            "q": "",  # пустой запрос - все посты, фильтровать в коде
            "count": count_per_request,
            "offset": offset,
            "v": VK_API_VERSION,
            "extended": 1,
            "fields": "city,description",
            "filters": "post"
        }

        try:
            response = requests.get(url, params=params).json()
            if 'error' in response:
                print(f"Ошибка VK API: {response['error'].get('error_msg')}")
                break

            items = response.get('response', {}).get('items', [])
            if not items:
                print("Постов не найдено, завершаем.")
                break

            for post in items:
                post_id = post['post_id'] if 'post_id' in post else post['id']
                owner_id = post['source_id']
                text = post.get('text', '')
                date = datetime.fromtimestamp(post['date']).strftime("%d.%m.%Y")

                # Проверяем кэш
                unique_post_id = f"{owner_id}_{post_id}"
                if unique_post_id in parsed_posts:
                    print(f"Пропускаем уже обработанный пост {unique_post_id}")
                    continue

                # Проверка по городу: пробуем найти название города в тексте или комментариях
                city_lower = city_name.lower()
                if city_lower not in text.lower():
                    # Можно добавить расширенную проверку, но пока простая фильтрация
                    print(f"Отброшен пост {unique_post_id}: город '{city_name}' не найден в тексте")
                    parsed_posts.add(unique_post_id)
                    continue

                # Рассчитываем баллы поста
                score, reasons = calculate_post_score(text)

                if score >= MIN_SCORE_THRESHOLD:
                    print(f"✅ Пост {unique_post_id} принят. Баллы: {score}. Причины: {reasons}")
                    # Сохраняем пост (можно добавить город и другую инфу)
                    add_shelter(unique_post_id, f"Группа {owner_id}", f"https://vk.com/wall{owner_id}_{post_id}", city_name, json.dumps({"date": date, "text": text[:500]}, ensure_ascii=False))
                    parsed_posts.add(unique_post_id)
                    total_added += 1
                    if total_added >= MAX_POSTS:
                        break
                else:
                    print(f"❌ Пост {unique_post_id} отклонён. Баллы: {score}. Причины: {reasons}")
                    parsed_posts.add(unique_post_id)

            offset += count_per_request
            time.sleep(0.4)  # API throttle

        except Exception as e:
            print(f"Ошибка при запросе постов: {e}")
            break

    save_cache()
    print(f"🏁 Поиск завершён. Добавлено постов: {total_added}")

if __name__ == "__main__":
    city = "Москва"  # пример города
    search_and_filter_posts(city)

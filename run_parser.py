from vk_parser import search_vk_groups
from update_favorite_posts import update_favorite_posts
from database import init_db
from time import time

CITIES = ["Новосибирск"]  # Можно менять

def update_all_cities():
    print("🚀 Запуск обновления приютов и избранных постов")
    init_db()
    start = time()

    for city in CITIES:
        print(f"🔄 Обновление города: {city}")
        try:
            search_vk_groups(city)
        except Exception as e:
            print(f"[!] Ошибка при обновлении города {city}: {e}")

    print("⭐ Обновление избранных постов")
    try:
        update_favorite_posts()
    except Exception as e:
        print(f"[!] Ошибка при обновлении избранных постов: {e}")

    print(f"✅ Все обновления завершены за {round(time() - start, 2)} секунд.")

from vk_parser import search_vk_groups
from update_favorite_posts import update_favorite_posts
from database import init_db

CITIES = ["Новосибирск"]  # Можно менять

def update_all_cities():
    print("🚀 Запуск обновления приютов и избранных постов")
    init_db()

    for city in CITIES:
        print(f"🔄 Обновление города: {city}")
        search_vk_groups(city)

    print("⭐ Обновление избранных постов")
    update_favorite_posts()

    print("✅ Все обновления завершены.")

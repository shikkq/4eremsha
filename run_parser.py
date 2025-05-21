from vk_parser import search_vk_groups
from database import init_db

CITIES = ["Новосибирск"]  # Можно менять

def update_all_cities():
    print("🚀 Запуск обновления приютов и избранных постов")
    init_db()

    for city in CITIES:
        print(f"🔄 Обновление города: {city}")
        search_vk_groups(city)

    print("✅ Все обновления завершены.")

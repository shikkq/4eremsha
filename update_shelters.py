from database import init_db
from vk_parser import search_vk_groups

CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань"]

if __name__ == "__main__":
    init_db()
    for city in CITIES:
        print(f"🔄 Обновляем данные по: {city}")
        search_vk_groups(city)
    print("✅ Обновление завершено.")

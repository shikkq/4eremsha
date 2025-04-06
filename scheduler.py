import schedule
import time
from vk_parser import search_vk_groups

# Список городов, которые ты хочешь парсить каждый день
CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань"]

def update_all_cities():
    print("🔄 Обновление приютов по городам...")
    for city in CITIES:
        print(f"📍 Обновляю {city}...")
        search_vk_groups(city)
        print(f"✅ Готово: {city}")

# Планируем запуск каждый день в 03:00
schedule.every().day.at("03:00").do(update_all_cities)

if __name__ == "__main__":
    print("📅 Планировщик запущен. Ожидаем следующего запуска...")
    while True:
        schedule.run_pending()
        time.sleep(60)

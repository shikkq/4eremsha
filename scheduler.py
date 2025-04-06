import schedule
import time
import sqlite3
import traceback

print("👋 Начинаем выполнение скрипта")

DEFAULT_CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань"]

try:
    from vk_parser import search_vk_groups
except Exception as e:
    print("❌ Ошибка импорта vk_parser:", e)
    traceback.print_exc()
    exit(1)

def update_all_cities():
    print("🔄 Обновление приютов по городам...")

    try:
        conn = sqlite3.connect("shelters.db")
        c = conn.cursor()
        c.execute("SELECT DISTINCT city FROM shelters")
        cities = [row[0] for row in c.fetchall()]
        conn.close()
    except Exception as e:
        print("⚠️ Ошибка базы, используем города по умолчанию:", e)
        traceback.print_exc()
        cities = DEFAULT_CITIES

    if not cities:
        cities = DEFAULT_CITIES

    for city in cities:
        print(f"📍 Обновляю {city}...")
        try:
            search_vk_groups(city)
        except Exception as e:
            print(f"❌ Ошибка при обновлении {city}:", e)
            traceback.print_exc()

schedule.every(1).minutes.do(update_all_cities)

if __name__ == "__main__":
    print("🚀 Первая проверка...")
    update_all_cities()

    print("⏳ Ожидаем следующее обновление...")
    while True:
        schedule.run_pending()
        time.sleep(10)

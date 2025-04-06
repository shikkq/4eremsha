import schedule
import time
import sqlite3
from vk_parser import search_vk_groups

def update_all_cities():
    print("🔄 Обновление приютов по городам...")
    conn = sqlite3.connect("shelters.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT city FROM shelters")
    cities = [row[0] for row in c.fetchall()]
    conn.close()

    for city in cities:
        print(f"📍 Обновляю {city}...")
        search_vk_groups(city)

schedule.every().day.at("03:00").do(update_all_cities)

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(60)

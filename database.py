import sqlite3
from datetime import datetime

DB_PATH = "shelters.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # таблица приютов
    c.execute("""
        CREATE TABLE IF NOT EXISTS shelters (
            id TEXT PRIMARY KEY,
            name TEXT,
            link TEXT,
            city TEXT,
            info TEXT
        )
    """)

    # таблица показанных приютов (для смены каждые 3 дня)
    c.execute("""
        CREATE TABLE IF NOT EXISTS shown_shelters (
            city TEXT,
            group_id TEXT,
            shown_date DATE
        )
    """)

    # таблица избранного
    c.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            post_url TEXT,
            group_id TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def add_shelter(id, name, link, city, info=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO shelters VALUES (?, ?, ?, ?, ?)", (id, name, link, city, info))
        conn.commit()
    except sqlite3.IntegrityError:
        # Приют уже есть
        pass
    conn.close()

from datetime import timedelta

def get_shelters_for_city(city, limit=20):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Проверяем, были ли уже показаны приюты для этого города
    cursor.execute("""
        SELECT group_id, shown_date FROM shown_shelters
        WHERE city = ?
    """, (city,))
    shown = cursor.fetchall()

    now = datetime.now().date()

    if shown:
        # Проверяем, прошло ли 3 дня
        shown_date = datetime.strptime(shown[0][1], "%Y-%m-%d").date()
        if (now - shown_date).days < 3:
            # Возвращаем уже показанные приюты
            ids = tuple([s[0] for s in shown])
            query = f"SELECT * FROM shelters WHERE id IN ({','.join(['?']*len(ids))})"
            cursor.execute(query, ids)
            result = cursor.fetchall()
            conn.close()
            return result

    # 2. Иначе — выбираем новые приюты
    cursor.execute("""
        SELECT * FROM shelters
        WHERE city = ?
        ORDER BY RANDOM()
        LIMIT ?
    """, (city, limit))
    result = cursor.fetchall()

    # 3. Обновляем таблицу shown_shelters
    cursor.execute("DELETE FROM shown_shelters WHERE city = ?", (city,))
    for row in result:
        cursor.execute("""
            INSERT INTO shown_shelters (city, group_id, shown_date)
            VALUES (?, ?, ?)
        """, (city, row[0], now.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

    return result

def add_favorite(user_id, post_url, group_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO favorites (user_id, post_url, group_id)
        VALUES (?, ?, ?)
    """, (user_id, post_url, group_id))
    conn.commit()
    conn.close()

def get_user_favorites(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_url, group_id FROM favorites
        WHERE user_id = ?
        ORDER BY added_at DESC
    """, (user_id,))
    favorites = cursor.fetchall()
    conn.close()
    return favorites


import sqlite3
from datetime import datetime, timedelta

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

    # таблица постов из избранных приютов
    c.execute("""
        CREATE TABLE IF NOT EXISTS favorite_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT,
            post_url TEXT UNIQUE,
            text TEXT,
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
        pass
    conn.close()

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
        shown_date = datetime.strptime(shown[0][1], "%Y-%m-%d").date()
        if (now - shown_date).days < 3:
            ids = [s[0] for s in shown]
            if ids:
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
        INSERT OR IGNORE INTO favorites (user_id, post_url, group_id)
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

def get_recent_posts_for_group(group_id, days=7):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cutoff = datetime.now() - timedelta(days=days)
    cursor.execute("""
        SELECT post_url, text FROM favorite_posts
        WHERE group_id = ? AND added_at >= ?
        ORDER BY added_at DESC
    """, (group_id, cutoff))
    posts = cursor.fetchall()
    conn.close()
    return posts

def get_favorite_group_ids():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT group_id FROM favorites")
    result = cursor.fetchall()
    conn.close()
    return [r[0] for r in result]

def post_already_saved(post_url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM favorite_posts WHERE post_url = ?", (post_url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_favorite_post(group_id, post_url, text):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO favorite_posts (group_id, post_url, text)
        VALUES (?, ?, ?)
    """, (group_id, post_url, text))
    conn.commit()
    conn.close()

def get_latest_favorite_posts(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_url, text FROM favorite_posts
        ORDER BY added_at DESC
        LIMIT ?
    """, (limit,))
    result = cursor.fetchall()
    conn.close()
    return result

# Для отладки (необязательно)
def list_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    conn.close()
    return [t[0] for t in tables]

if __name__ == "__main__":
    init_db()

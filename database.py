import sqlite3
from datetime import datetime, timedelta

DB_PATH = "shelters.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Таблица приютов: добавлено поле post_date для хранения даты поста
    c.execute("""
        CREATE TABLE IF NOT EXISTS shelters (
            id TEXT PRIMARY KEY,
            name TEXT,
            link TEXT,
            city TEXT,
            info TEXT,
            post_date TEXT
        )
    """)

    # Таблица показанных приютов (для смены каждые 3 дня, используется только если нужно историю)
    c.execute("""
        CREATE TABLE IF NOT EXISTS shown_shelters (
            city TEXT,
            group_id TEXT,
            shown_date DATE
        )
    """)

    # Таблица избранного
    c.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            post_url TEXT,
            group_id TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица постов из избранных приютов
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

def add_shelter(id, name, link, city, info="", post_date=""):
    """
    Добавляет запись о приюте в базу.
    Если запись с таким id уже существует, она не перезаписывается.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO shelters VALUES (?, ?, ?, ?, ?, ?)", (id, name, link, city, info, post_date))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def get_filtered_shelters(city: str, filter_keyword: str):
    """
    Возвращает приюты для указанного города, у которых в info встречается ключевое слово.
    """
    conn = sqlite3.connect("shelters.db")
    c = conn.cursor()
    c.execute(
        "SELECT id, name FROM shelters WHERE city = ? AND info LIKE ?",
        (city, f"%{filter_keyword}%")
    )
    results = c.fetchall()
    conn.close()
    return results

def get_shelters_for_city(city, limit=20):
    """
    Возвращает список приютов для указанного города.
    Теперь НЕ фильтрует по таблице shown_shelters – выводятся все записи,
    отсортированные по дате поста (сначала самые свежие).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Если поле post_date заполнено, сортируем по нему, иначе по ROWID
    cursor.execute("""
        SELECT * FROM shelters
        WHERE city = ?
        ORDER BY CASE 
                    WHEN post_date != '' THEN datetime(post_date)
                    ELSE ROWID
                 END DESC
        LIMIT ?
    """, (city, limit))
    result = cursor.fetchall()
    conn.close()
    return result

def get_shelter_by_id(shelter_id):
    """
    Возвращает запись по идентификатору приюта в виде кортежа:
      (name, link, info, post_date)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, link, info, post_date FROM shelters WHERE id = ?", (shelter_id,))
    row = cursor.fetchone()
    conn.close()
    return row

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

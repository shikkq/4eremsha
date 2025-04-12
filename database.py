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

    # Таблица показанных приютов (для смены каждые 3 дня, используется только если нужна история)
    c.execute("""
        CREATE TABLE IF NOT EXISTS shown_shelters (
            city TEXT,
            group_id TEXT,
            shown_date DATE
        )
    """)

    # Таблица пользовательских городов (сохранение городов, введённых пользователями)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_cities (
            user_id INTEGER,
            city TEXT,
            UNIQUE(user_id, city)
        )
    """)

    # Таблица сохранённых постов (для команды /fav)
    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            post_url TEXT UNIQUE,
            group_id TEXT,
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

def add_user_city(user_id, city):
    """
    Добавляет город, введённый пользователем, в таблицу user_cities.
    Название города нормализуется (первая буква заглавная, без лишних пробелов).
    """
    normalized_city = city.strip().title()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO user_cities (user_id, city) VALUES (?, ?)", (user_id, normalized_city))
        conn.commit()
    except Exception as e:
        print("Ошибка добавления города:", e)
    conn.close()

def get_user_cities(user_id):
    """
    Возвращает список городов, сохранённых для данного пользователя.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT city FROM user_cities WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_filtered_shelters(city: str, filter_keyword: str):
    """
    Возвращает приюты для указанного города, у которых в поле info встречается filter_keyword.
    """
    conn = sqlite3.connect(DB_PATH)
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
    Запрос не использует таблицу shown_shelters – выводятся все записи,
    отсортированные по дате поста (сначала самые свежие).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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

def save_post(user_id, post_url, group_id, text):
    """
    Сохраняет пост для пользователя (используется командой /fav).
    Если пост с таким post_url уже сохранён, не перезаписывает его.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO saved_posts (user_id, post_url, group_id, text)
        VALUES (?, ?, ?, ?)
    """, (user_id, post_url, group_id, text))
    conn.commit()
    conn.close()

def get_user_saved_posts(user_id):
    """
    Возвращает сохранённые посты пользователя.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_url, text FROM saved_posts
        WHERE user_id = ?
        ORDER BY added_at DESC
    """, (user_id,))
    posts = cursor.fetchall()
    conn.close()
    return posts

def get_recent_posts_for_group(group_id, days=7):
    """
    Возвращает сохранённые посты для группы, добавленные за последние days дней.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cutoff = datetime.now() - timedelta(days=days)
    cursor.execute("""
        SELECT post_url, text FROM saved_posts
        WHERE group_id = ? AND added_at >= ?
        ORDER BY added_at DESC
    """, (group_id, cutoff))
    posts = cursor.fetchall()
    conn.close()
    return posts

def list_tables():
    """
    Для отладки: возвращает список таблиц в базе.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    conn.close()
    return [t[0] for t in tables]

if __name__ == "__main__":
    init_db()

import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any

DB_PATH = "shelters.db"

def init_db():
    """Инициализация базы данных с улучшенной обработкой ошибок"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS shelters (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                city TEXT NOT NULL COLLATE NOCASE,
                info TEXT DEFAULT '',
                post_date DATETIME
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS shown_shelters (
                city TEXT NOT NULL COLLATE NOCASE,
                group_id TEXT NOT NULL,
                shown_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (city, group_id)
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_cities (
                user_id INTEGER NOT NULL,
                city TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY (user_id, city)
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS saved_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                post_url TEXT NOT NULL UNIQUE,
                group_id TEXT NOT NULL,
                text TEXT NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Индексы
        c.execute("CREATE INDEX IF NOT EXISTS idx_shelters_city ON shelters(city)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_shelters_post_date ON shelters(post_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_saved_posts_user ON saved_posts(user_id)")

        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

def add_shelter(shelter_id: str, name: str, link: str, city: str, 
               info: str = "", post_date: Optional[datetime] = None) -> bool:
    """Добавляет приют в базу данных"""
    conn = None
    try:
        city = city.strip().title()
        post_date_str = post_date.isoformat() if post_date else None
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO shelters (id, name, link, city, info, post_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
        """, (shelter_id, name, link, city, info, post_date_str))
        
        conn.commit()
        return c.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error adding shelter: {e}")
        return False
    finally:
        if conn:
            conn.close()

def add_user_city(user_id: int, city: str) -> bool:
    """Добавляет город пользователя"""
    normalized_city = city.strip().title()
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO user_cities (user_id, city)
            VALUES (?, ?)
        """, (user_id, normalized_city))
        conn.commit()
        return c.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error adding city: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_user_cities(user_id: int) -> List[str]:
    """Возвращает города пользователя"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT city FROM user_cities WHERE user_id = ?", (user_id,))
        return [row[0] for row in c.fetchall()]
    except sqlite3.Error as e:
        print(f"Error getting cities: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_filtered_shelters(city: str, filter_keyword: str) -> List[Tuple]:
    """Фильтрация приютов по ключевому слову"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT id, name FROM shelters 
            WHERE city = ? AND info LIKE ?
        """, (city.strip().title(), f"%{filter_keyword}%"))
        return c.fetchall()
    except sqlite3.Error as e:
        print(f"Error filtering shelters: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_shelters_for_city(city: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Получение приютов для города"""
    city = city.strip().title()
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT * FROM shelters
            WHERE city = ?
            ORDER BY post_date DESC
            LIMIT ?
        """, (city, limit))
        return [dict(row) for row in c.fetchall()]
    except sqlite3.Error as e:
        print(f"Error getting shelters: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_shelter_by_id(shelter_id: str) -> Optional[Tuple]:
    """Получение приюта по ID"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name, link, info, post_date FROM shelters WHERE id = ?", (shelter_id,))
        return c.fetchone()
    except sqlite3.Error as e:
        print(f"Error getting shelter: {e}")
        return None
    finally:
        if conn:
            conn.close()

def save_post(user_id: int, post_url: str, group_id: str, text: str) -> bool:
    """Сохранение поста"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO saved_posts 
            (user_id, post_url, group_id, text)
            VALUES (?, ?, ?, ?)
        """, (user_id, post_url, group_id, text.strip()))
        conn.commit()
        return c.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error saving post: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_user_saved_posts(user_id: int) -> List[Tuple]:
    """Получение сохраненных постов"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT post_url, text FROM saved_posts
            WHERE user_id = ?
            ORDER BY added_at DESC
        """, (user_id,))
        return c.fetchall()
    except sqlite3.Error as e:
        print(f"Error getting posts: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_recent_posts_for_group(group_id: str, days: int = 7) -> List[Tuple]:
    """Получение свежих постов группы"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        c.execute("""
            SELECT post_url, text FROM saved_posts
            WHERE group_id = ? AND added_at >= ?
            ORDER BY added_at DESC
        """, (group_id, cutoff))
        return c.fetchall()
    except sqlite3.Error as e:
        print(f"Error getting recent posts: {e}")
        return []
    finally:
        if conn:
            conn.close()

def list_tables() -> List[str]:
    """Список таблиц (для отладки)"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in c.fetchall()]
    except sqlite3.Error as e:
        print(f"Error listing tables: {e}")
        return []
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized. Tables:", list_tables())

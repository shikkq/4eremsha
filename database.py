import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

DB_PATH = "shelters.db"

# Добавим проверку существования файла БД
def init_db():
    """Инициализация базы данных с улучшенной обработкой ошибок"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Улучшенные таблицы с индексами
        c.execute("""
            CREATE TABLE IF NOT EXISTS shelters (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                city TEXT NOT NULL COLLATE NOCASE,
                info TEXT DEFAULT '',
                post_date DATETIME  -- Изменен тип на DATETIME
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS shown_shelters (
                city TEXT NOT NULL COLLATE NOCASE,
                group_id TEXT NOT NULL,
                shown_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (city, group_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_cities (
                user_id INTEGER NOT NULL,
                city TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY (user_id, city)
            )
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

        # Создаем индексы для часто используемых полей
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
    """
    Добавляет приют с улучшенной обработкой дат
    Возвращает True при успешном добавлении
    """
    conn = None
    try:
        # Нормализация данных
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

# Остальные функции должны быть аналогично модифицированы с:
# 1. Нормализацией ввода (особенно для городов)
# 2. Правильной обработкой дат
# 3. Использованием типизации
# 4. Улучшенной обработкой ошибок

def get_shelters_for_city(city: str, limit: int = 20) -> List[Tuple]:
    """
    Получение приютов с улучшенной обработкой города
    """
    city = city.strip().title()
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM shelters
            WHERE city = ?
            ORDER BY post_date DESC
            LIMIT ?
        """, (city, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db()

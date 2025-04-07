import sqlite3
from vk_parser import get_group_posts  # ты уже это используешь
from datetime import datetime, timedelta

DB_PATH = "shelters.db"

def get_favorite_group_ids():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT group_id FROM favorites")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def post_already_saved(post_url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM favorite_posts WHERE post_url=?", (post_url,))
    exists = c.fetchone()
    conn.close()
    return exists is not None

def save_favorite_post(group_id, post_url, text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO favorite_posts (group_id, post_url, text) VALUES (?, ?, ?)",
              (group_id, post_url, text))
    conn.commit()
    conn.close()

def is_relevant(text):
    text = text.lower()
    keywords = ["волонтёр", "помощь", "приходите", "корм", "сбор", "лекарства", "деньги"]
    return any(kw in text for kw in keywords)

def update_favorite_posts():
    group_ids = get_favorite_group_ids()

    for group_id in group_ids:
        try:
            posts = get_group_posts(group_id, count=10)
            for post in posts:
                date = datetime.fromtimestamp(post['date'])
                if datetime.now() - date > timedelta(days=2):
                    continue

                text = post.get('text', '')
                post_url = f"https://vk.com/wall-{group_id}_{post['id']}"

                if not post_already_saved(post_url) and is_relevant(text):
                    save_favorite_post(group_id, post_url, text)
                    print(f"Сохранён новый пост: {post_url}")

        except Exception as e:
            print(f"[!] Ошибка при обработке группы {group_id}: {e}")

if __name__ == "__main__":
    update_favorite_posts()

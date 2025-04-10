import sqlite3
from vk_parser import get_group_posts, extract_info_from_posts
from datetime import datetime, timedelta

DB_PATH = "shelters.db"

def get_favorite_group_ids():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT group_id FROM favorites")
    rows = c.fetchall()
    conn.close()
    return [r[0].replace("vk_", "") for r in rows if r[0].startswith("vk_")]

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
              (f"vk_{group_id}", post_url, text))
    conn.commit()
    conn.close()

def update_favorite_posts():
    group_ids = get_favorite_group_ids()
    print(f"🔄 Обновление избранных: {len(group_ids)} групп")

    for group_id in group_ids:
        try:
            posts = get_group_posts(int(group_id))
            recent_posts = [
                post for post in posts
                if datetime.now() - datetime.fromtimestamp(post['date']) < timedelta(days=2)
            ]

            if not recent_posts:
                print(f"⏳ В группе {group_id} нет свежих постов")
                continue

            info = extract_info_from_posts(recent_posts, city_name="")
            if info:
                newest_post = max(recent_posts, key=lambda p: p["date"])
                post_url = f"https://vk.com/wall-{group_id}_{newest_post['id']}"

                if not post_already_saved(post_url):
                    save_favorite_post(group_id, post_url, info)
                    print(f"✅ Сохранён новый пост: {post_url}")
                else:
                    print(f"ℹ️ Уже сохранён: {post_url}")
            else:
                print(f"⚠️ Нет подходящей информации для группы {group_id}")

        except Exception as e:
            print(f"[!] Ошибка при обработке группы {group_id}: {e}")

if __name__ == "__main__":
    update_favorite_posts()

import sqlite3

def init_db():
    conn = sqlite3.connect("shelters.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS shelters (
            id TEXT PRIMARY KEY,
            name TEXT,
            link TEXT,
            city TEXT,
            info TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_shelter(id, name, link, city, info=""):
    conn = sqlite3.connect("shelters.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO shelters VALUES (?, ?, ?, ?, ?)", (id, name, link, city, info))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

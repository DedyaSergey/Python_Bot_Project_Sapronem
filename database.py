import sqlite3

conn = sqlite3.connect("")
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reputation (
        chat_id INTEGER,
        user_id INTEGER,
        user_name TEXT,
        karma INTEGER DEFAULT 0,
        messages_all INTEGER DEFAULT 0,
        dice_score INTEGER DEFAULT 0,
        warns INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        age INTEGER,
        city TEXT,
        bio TEXT,
        photo_id TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS marriages (
        chat_id INTEGER,
        user1_id INTEGER,
        user2_id INTEGER,
        user1_name TEXT,
        user2_name TEXT,
        PRIMARY KEY (chat_id, user1_id, user2_id)
    )
    """)
    # Новая таблица для триггеров (ключевых слов)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS triggers (
        chat_id INTEGER,
        keyword TEXT,
        reply_text TEXT,
        PRIMARY KEY (chat_id, keyword)
    )
    """)
    conn.commit()

# --- ФУНКЦИИ ДЛЯ ТРИГГЕРОВ ---
def add_trigger(chat_id, keyword, reply_text):
    cursor.execute("""
    INSERT INTO triggers (chat_id, keyword, reply_text)
    VALUES (?, ?, ?)
    ON CONFLICT(chat_id, keyword) DO UPDATE SET reply_text = ?
    """, (chat_id, keyword, reply_text, reply_text))
    conn.commit()

def get_trigger(chat_id, keyword):
    cursor.execute("SELECT reply_text FROM triggers WHERE chat_id = ? AND keyword = ?", (chat_id, keyword))
    result = cursor.fetchone()
    return result[0] if result else None

def delete_trigger(chat_id, keyword):
    cursor.execute("DELETE FROM triggers WHERE chat_id = ? AND keyword = ?", (chat_id, keyword))
    conn.commit()

# --- ФУНКЦИИ ДЛЯ БРАКОВ ---
def create_marriage(chat_id, u1_id, u1_name, u2_id, u2_name):
    cursor.execute("""
    INSERT INTO marriages (chat_id, user1_id, user2_id, user1_name, user2_name)
    VALUES (?, ?, ?, ?, ?)
    """, (chat_id, u1_id, u1_name, u2_id, u2_name))
    conn.commit()

def check_marriage(chat_id, user_id):
    """Проверяет, состоит ли юзер в браке в этом чате"""
    cursor.execute("""
    SELECT user1_name, user2_name FROM marriages 
    WHERE chat_id = ? AND (user1_id = ? OR user2_id = ?)
    """, (chat_id, user_id, user_id))
    return cursor.fetchone()

def delete_marriage(chat_id, user_id):
    cursor.execute("""
    DELETE FROM marriages 
    WHERE chat_id = ? AND (user1_id = ? OR user2_id = ?)
    """, (chat_id, user_id, user_id))
    conn.commit()


def add_warn(chat_id, user_id):
    """Добавляет 1 варн и возвращает текущее количество"""
    cursor.execute("SELECT warns FROM reputation WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    result = cursor.fetchone()
    current_warns = result[0] if result else 0
    new_warns = current_warns + 1
    
    cursor.execute("""
    INSERT INTO reputation (chat_id, user_id, warns) VALUES (?, ?, ?)
    ON CONFLICT(chat_id, user_id) DO UPDATE SET warns = warns + 1
    """, (chat_id, user_id, new_warns))
    conn.commit()
    return new_warns

def reset_warns(chat_id, user_id):
    """Сбрасывает варны в 0"""
    cursor.execute("UPDATE reputation SET warns = 0 WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    conn.commit()

def log_message(chat_id, user_id, user_name):
    cursor.execute("""
    INSERT INTO reputation (chat_id, user_id, user_name, messages_all) 
    VALUES (?, ?, ?, 1) 
    ON CONFLICT(chat_id, user_id) DO UPDATE SET 
        messages_all = messages_all + 1,
        user_name = ?
    """, (chat_id, user_id, user_name, user_name))
    conn.commit()

def get_karma(chat_id, user_id):
    cursor.execute("SELECT karma FROM reputation WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    result = cursor.fetchone()
    return result if result else 0

def update_karma(chat_id, user_id, change):
    cursor.execute("""
    INSERT INTO reputation (chat_id, user_id, karma) 
    VALUES (?, ?, ?) 
    ON CONFLICT(chat_id, user_id) DO UPDATE SET karma = karma + ?
    """, (chat_id, user_id, change, change))
    conn.commit()
    return get_karma(chat_id, user_id)

def get_top_messages(chat_id, limit=10):
    cursor.execute("""
    SELECT user_name, messages_all FROM reputation 
    WHERE chat_id = ? AND messages_all > 0
    ORDER BY messages_all DESC LIMIT ?
    """, (chat_id, limit))
    return cursor.fetchall()

def save_profile(user_id, name, age, city, bio, photo_id):
    cursor.execute("""
    INSERT INTO profiles (user_id, name, age, city, bio, photo_id) 
    VALUES (?, ?, ?, ?, ?, ?) 
    ON CONFLICT(user_id) DO UPDATE SET name=?, age=?, city=?, bio=?, photo_id=?
    """, (user_id, name, age, city, bio, photo_id, name, age, city, bio, photo_id))
    conn.commit()

def get_profile(user_id):
    cursor.execute("SELECT name, age, city, bio, photo_id FROM profiles WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def update_dice(chat_id, user_id, user_name, score):
    cursor.execute("""
    INSERT INTO reputation (chat_id, user_id, user_name, dice_score) 
    VALUES (?, ?, ?, ?) 
    ON CONFLICT(chat_id, user_id) DO UPDATE SET 
        dice_score = dice_score + ?,
        user_name = ?
    """, (chat_id, user_id, user_name, score, score, user_name))
    conn.commit()

def get_top_dice(chat_id, limit=10):
    cursor.execute("""
    SELECT user_name, dice_score FROM reputation 
    WHERE chat_id = ? AND dice_score > 0
    ORDER BY dice_score DESC LIMIT ?
    """, (chat_id, limit))
    return cursor.fetchall()

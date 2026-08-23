import sqlite3
import time
import os

# Путь к файлу базы. По умолчанию — "bot.db" рядом с кодом (подходит для
# локального запуска). На Railway ОБЯЗАТЕЛЬНО подключи Volume (постоянный
# диск) и укажи путь к нему через переменную окружения DB_PATH, иначе при
# каждом редеплое/рестарте контейнера база будет создаваться с нуля и вся
# карма/монеты/ферма обнулятся.
#
# Как настроить на Railway:
#   1. В проекте сервиса открой вкладку "Volumes" -> "New Volume".
#   2. Укажи Mount Path, например: /data
#   3. Во вкладке "Variables" добавь: DB_PATH = /data/bot.db
DB_PATH = os.getenv("DB_PATH", "bot.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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

    # Миграция: добавляем колонку coins, если её ещё нет (для уже существующей базы)
    try:
        cursor.execute("ALTER TABLE reputation ADD COLUMN coins INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # колонка уже есть

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

    # Таблица фермы: у каждого юзера в чате несколько грядок (plot_number)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farms (
        chat_id INTEGER,
        user_id INTEGER,
        plot_number INTEGER,
        crop TEXT,
        planted_at INTEGER,
        PRIMARY KEY (chat_id, user_id, plot_number)
    )
    """)

    # Глобальные данные пользователя: рефералы и первый вход.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_meta (
        user_id INTEGER PRIMARY KEY,
        referred_by INTEGER,
        first_seen INTEGER NOT NULL
    )
    """)

    # Экономика конкретного чата: стартовый бонус и ежедневный бонус.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS economy_meta (
        chat_id INTEGER,
        user_id INTEGER,
        starter_claimed INTEGER DEFAULT 0,
        daily_bonus_at INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )
    """)

    # Одноразовые награды за рефералы.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referral_rewards (
        user_id INTEGER PRIMARY KEY,
        reward_claimed INTEGER DEFAULT 0
    )
    """)

    # Глобальная премиальная валюта Sapronem и VIP.
    # Она не зависит от конкретной группы, в отличие от обычных 🪙 монет фермы.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS premium_wallet (
        user_id INTEGER PRIMARY KEY,
        sapy INTEGER DEFAULT 0,
        vip_until INTEGER DEFAULT 0
    )
    """)

    # История покупок за Telegram Stars. telegram_payment_charge_id уникален,
    # поэтому повторная доставка одного платежа не начислит сапы второй раз.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS star_payments (
        telegram_payment_charge_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        payload TEXT NOT NULL,
        stars INTEGER NOT NULL,
        sapy INTEGER NOT NULL,
        created_at INTEGER NOT NULL
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
    return result[0] if result else 0

def update_karma(chat_id, user_id, change):
    cursor.execute("""
    INSERT INTO reputation (chat_id, user_id, karma) 
    VALUES (?, ?, ?) 
    ON CONFLICT(chat_id, user_id) DO UPDATE SET karma = karma + ?
    """, (chat_id, user_id, change, change))
    conn.commit()
    return get_karma(chat_id, user_id)

def get_top_messages(chat_id, limit=10):
    """Возвращает (user_id, user_name, messages_all) — user_id нужен для кликабельного упоминания"""
    cursor.execute("""
    SELECT user_id, user_name, messages_all FROM reputation 
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


# --- ФУНКЦИИ ДЛЯ МОНЕТ (валюта фермы) ---
def get_coins(chat_id, user_id):
    cursor.execute("SELECT coins FROM reputation WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    result = cursor.fetchone()
    return result[0] if result else 0

def add_coins(chat_id, user_id, amount):
    """amount может быть отрицательным (списание за семена)"""
    cursor.execute("""
    INSERT INTO reputation (chat_id, user_id, coins) 
    VALUES (?, ?, ?) 
    ON CONFLICT(chat_id, user_id) DO UPDATE SET coins = coins + ?
    """, (chat_id, user_id, amount, amount))
    conn.commit()
    return get_coins(chat_id, user_id)


# --- ГЛОБАЛЬНЫЕ ДАННЫЕ / РЕФЕРАЛЫ ---
def register_user(user_id, referred_by=None):
    """Регистрирует пользователя при первом запуске и сохраняет реферера."""
    now = int(time.time())
    cursor.execute("SELECT referred_by FROM user_meta WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is not None:
        return row[0]

    # Нельзя пригласить самого себя.
    if referred_by == user_id:
        referred_by = None
    cursor.execute(
        "INSERT INTO user_meta (user_id, referred_by, first_seen) VALUES (?, ?, ?)",
        (user_id, referred_by, now),
    )
    conn.commit()
    return referred_by


def get_referral_count(user_id):
    cursor.execute("SELECT COUNT(*) FROM user_meta WHERE referred_by = ?", (user_id,))
    return cursor.fetchone()[0]


def get_referral_inviter(user_id):
    cursor.execute("SELECT referred_by FROM user_meta WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def get_referral_reward_claimed(user_id):
    cursor.execute("SELECT reward_claimed FROM referral_rewards WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return bool(row[0]) if row else False


def claim_referral_reward(user_id):
    cursor.execute("""
    INSERT INTO referral_rewards (user_id, reward_claimed) VALUES (?, 1)
    ON CONFLICT(user_id) DO UPDATE SET reward_claimed = 1
    """, (user_id,))
    conn.commit()


def ensure_economy_user(chat_id, user_id):
    """Возвращает True, если пользователю только что выдан стартовый бонус."""
    cursor.execute(
        "SELECT starter_claimed FROM economy_meta WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    )
    row = cursor.fetchone()
    if row is not None:
        return False
    cursor.execute(
        "INSERT INTO economy_meta (chat_id, user_id, starter_claimed, daily_bonus_at) VALUES (?, ?, 1, 0)",
        (chat_id, user_id),
    )
    conn.commit()
    add_coins(chat_id, user_id, 100)
    return True


def claim_daily_bonus(chat_id, user_id, amount=100, cooldown=86400):
    """Возвращает (claimed, seconds_left)."""
    now = int(time.time())
    ensure_economy_user(chat_id, user_id)
    cursor.execute(
        "SELECT daily_bonus_at FROM economy_meta WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    )
    row = cursor.fetchone()
    last = row[0] if row else 0
    if last and now - last < cooldown:
        return False, cooldown - (now - last)
    cursor.execute(
        "UPDATE economy_meta SET daily_bonus_at = ? WHERE chat_id = ? AND user_id = ?",
        (now, chat_id, user_id),
    )
    conn.commit()
    add_coins(chat_id, user_id, amount)
    return True, 0


def get_economy_status(chat_id, user_id):
    cursor.execute(
        "SELECT starter_claimed, daily_bonus_at FROM economy_meta WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    )
    return cursor.fetchone() or (0, 0)


# --- ГЛОБАЛЬНАЯ ВАЛЮТА И VIP ---
def ensure_premium_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO premium_wallet (user_id, sapy, vip_until) VALUES (?, 0, 0)", (user_id,))
    conn.commit()


def get_sapy(user_id):
    ensure_premium_user(user_id)
    cursor.execute("SELECT sapy FROM premium_wallet WHERE user_id = ?", (user_id,))
    return cursor.fetchone()[0]


def add_sapy(user_id, amount):
    ensure_premium_user(user_id)
    cursor.execute("UPDATE premium_wallet SET sapy = MAX(0, sapy + ?) WHERE user_id = ?", (amount, user_id))
    conn.commit()
    return get_sapy(user_id)


def apply_star_payment(user_id, charge_id, payload, stars, sapy):
    """Начисляет сапы за подтверждённый Telegram Stars-платёж ровно один раз."""
    ensure_premium_user(user_id)
    now = int(time.time())
    try:
        cursor.execute("""
        INSERT INTO star_payments(telegram_payment_charge_id, user_id, payload, stars, sapy, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (charge_id, user_id, payload, stars, sapy, now))
        cursor.execute("UPDATE premium_wallet SET sapy = sapy + ? WHERE user_id = ?", (sapy, user_id))
        conn.commit()
        return True, get_sapy(user_id)
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, get_sapy(user_id)


def spend_sapy(user_id, amount):
    ensure_premium_user(user_id)
    cursor.execute("UPDATE premium_wallet SET sapy = sapy - ? WHERE user_id = ? AND sapy >= ?", (amount, user_id, amount))
    changed = cursor.rowcount > 0
    conn.commit()
    return changed


def get_vip_until(user_id):
    ensure_premium_user(user_id)
    cursor.execute("SELECT vip_until FROM premium_wallet WHERE user_id = ?", (user_id,))
    return cursor.fetchone()[0]


def is_vip(user_id):
    return get_vip_until(user_id) > int(time.time())


def activate_vip(user_id, days=30):
    ensure_premium_user(user_id)
    now = int(time.time())
    current = get_vip_until(user_id)
    start = max(now, current)
    until = start + days * 86400
    cursor.execute("UPDATE premium_wallet SET vip_until = ? WHERE user_id = ?", (until, user_id))
    conn.commit()
    return until


def buy_vip(user_id, price=100, days=30):
    if not spend_sapy(user_id, price):
        return False, get_sapy(user_id), get_vip_until(user_id)
    until = activate_vip(user_id, days)
    return True, get_sapy(user_id), until


def vip_seconds_left(user_id):
    return max(0, get_vip_until(user_id) - int(time.time()))


# --- ФУНКЦИИ ДЛЯ ФЕРМЫ ---
FARM_PLOTS = 3  # обычный лимит; VIP получает +1 грядку

def get_farm(chat_id, user_id):
    """Возвращает список из FARM_PLOTS элементов: (plot_number, crop, planted_at) или (plot_number, None, None)"""
    cursor.execute("""
    SELECT plot_number, crop, planted_at FROM farms 
    WHERE chat_id = ? AND user_id = ?
    """, (chat_id, user_id))
    existing = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    plots = []
    plot_limit = FARM_PLOTS + (1 if is_vip(user_id) else 0)
    for i in range(1, plot_limit + 1):
        crop, planted_at = existing.get(i, (None, None))
        plots.append((i, crop, planted_at))
    return plots

def plant_crop(chat_id, user_id, plot_number, crop):
    planted_at = int(time.time())
    cursor.execute("""
    INSERT INTO farms (chat_id, user_id, plot_number, crop, planted_at)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(chat_id, user_id, plot_number) DO UPDATE SET crop = ?, planted_at = ?
    """, (chat_id, user_id, plot_number, crop, planted_at, crop, planted_at))
    conn.commit()

def clear_plot(chat_id, user_id, plot_number):
    cursor.execute("""
    DELETE FROM farms WHERE chat_id = ? AND user_id = ? AND plot_number = ?
    """, (chat_id, user_id, plot_number))
    conn.commit()

# --- МАГАЗИН SAPRONEM ---
def init_shop_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shop_items (
        item_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        price INTEGER NOT NULL,
        item_type TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_inventory (
        user_id INTEGER,
        item_id TEXT,
        quantity INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, item_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_cosmetics (
        user_id INTEGER PRIMARY KEY,
        title TEXT
    )
    """)
    items = [
        ("title_star", "🌟 Титул «Звезда»", "Показывается в профиле.", 50, "title"),
        ("title_farmer", "🌾 Титул «Фермер»", "Показывается в профиле.", 75, "title"),
        ("vip_30", "👑 VIP на 30 дней", "+1 грядка, увеличенный ежедневный бонус и VIP-статус.", 100, "vip"),
        ("vip_90", "👑 VIP на 90 дней", "VIP сразу на 3 месяца.", 250, "vip"),
        ("gift_pack", "🎁 Подарочный набор", "Одноразовый набор: можно подарить другу 25 💎.", 30, "gift"),
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO shop_items(item_id, name, description, price, item_type)
    VALUES (?, ?, ?, ?, ?)
    """, items)
    conn.commit()


def get_shop_items():
    cursor.execute("SELECT item_id, name, description, price, item_type FROM shop_items ORDER BY price")
    return cursor.fetchall()


def buy_shop_item(user_id, item_id):
    ensure_premium_user(user_id)
    cursor.execute("SELECT name, description, price, item_type FROM shop_items WHERE item_id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        return False, "Товар не найден", get_sapy(user_id)
    name, description, price, item_type = item
    if not spend_sapy(user_id, price):
        return False, f"Не хватает сапов. Нужно {price} 💎, у тебя {get_sapy(user_id)} 💎.", get_sapy(user_id)

    if item_type == "vip":
        days = 90 if item_id == "vip_90" else 30
        activate_vip(user_id, days)
    elif item_type == "title":
        title = "🌟 Звезда" if item_id == "title_star" else "🌾 Фермер"
        cursor.execute("""
        INSERT INTO user_cosmetics(user_id, title) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET title = excluded.title
        """, (user_id, title))
        conn.commit()
    else:
        cursor.execute("""
        INSERT INTO user_inventory(user_id, item_id, quantity) VALUES (?, ?, 1)
        ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + 1
        """, (user_id, item_id))
        conn.commit()
    return True, name, get_sapy(user_id)


def get_user_title(user_id):
    cursor.execute("SELECT title FROM user_cosmetics WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def get_inventory_quantity(user_id, item_id):
    cursor.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    row = cursor.fetchone()
    return row[0] if row else 0


def use_gift_pack(user_id, target_id):
    if target_id == user_id:
        return False, "Нельзя подарить набор самому себе."
    if get_inventory_quantity(user_id, "gift_pack") < 1:
        return False, "У тебя нет подарочного набора."
    cursor.execute("UPDATE user_inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ? AND quantity > 0", (user_id, "gift_pack"))
    add_sapy(target_id, 25)
    conn.commit()
    return True, "🎁 Друг получил 25 💎 сапов!"


# Инициализируем магазин после создания базовых таблиц.
init_shop_db()

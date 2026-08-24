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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_activity (
        user_id INTEGER PRIMARY KEY,
        last_seen INTEGER NOT NULL,
        last_chat_id INTEGER DEFAULT 0,
        message_count INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_quests (
        chat_id INTEGER,
        user_id INTEGER,
        day_key TEXT,
        quest_type TEXT,
        progress INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id, day_key)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS season_points (
        season_id TEXT,
        chat_id INTEGER,
        user_id INTEGER,
        points INTEGER DEFAULT 0,
        PRIMARY KEY (season_id, chat_id, user_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS season_rewards (
        season_id TEXT,
        chat_id INTEGER,
        user_id INTEGER,
        place INTEGER,
        claimed INTEGER DEFAULT 0,
        PRIMARY KEY (season_id, chat_id, user_id)
    )
    """)

    # Глобальный сезон: единый рейтинг игрока сразу по всем группам.
    # chat_id = 0 в season_rewards/season_achievements используется как
    # глобальная область, чтобы награда не могла быть получена повторно
    # в разных чатах.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS global_season_config (
        id INTEGER PRIMARY KEY CHECK(id = 1),
        enabled INTEGER DEFAULT 0,
        season_name TEXT DEFAULT '',
        rewards_json TEXT DEFAULT ''
    )
    """)
    cursor.execute("INSERT OR IGNORE INTO global_season_config(id, enabled, season_name, rewards_json) VALUES(1, 0, '', '')")
    # Миграция старых баз: добавляем настройки глобального сезона.
    for column, ddl in (("season_name", "TEXT DEFAULT ''"), ("rewards_json", "TEXT DEFAULT ''")):
        try:
            cursor.execute(f"ALTER TABLE global_season_config ADD COLUMN {column} {ddl}")
        except sqlite3.OperationalError:
            pass
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS global_season_settings (
        season_id TEXT PRIMARY KEY,
        season_name TEXT DEFAULT '',
        rewards_json TEXT DEFAULT ''
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_sapy_weekly (
        admin_id INTEGER,
        week_key TEXT,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY (admin_id, week_key)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        admin_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target_id INTEGER,
        amount INTEGER DEFAULT 0,
        details TEXT DEFAULT '',
        created_at INTEGER NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_settings (
        chat_id INTEGER PRIMARY KEY,
        farm_enabled INTEGER DEFAULT 1,
        quests_enabled INTEGER DEFAULT 1,
        seasons_enabled INTEGER DEFAULT 1,
        events_enabled INTEGER DEFAULT 1,
        economy_enabled INTEGER DEFAULT 1
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS global_season_points (
        season_id TEXT,
        user_id INTEGER,
        points INTEGER DEFAULT 0,
        PRIMARY KEY (season_id, user_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS season_achievements (
        season_id TEXT,
        chat_id INTEGER,
        user_id INTEGER,
        place INTEGER,
        title TEXT,
        PRIMARY KEY (season_id, chat_id, user_id)
    )
    """)
    conn.commit()

# --- ФУНКЦИИ ДЛЯ ЕЖЕДНЕВНЫХ ЗАДАНИЙ, СЕЗОНОВ И СОБЫТИЙ ---
def current_day_key():
    return time.strftime("%Y-%m-%d", time.localtime())

def current_season_id():
    return time.strftime("%G-W%V", time.localtime())

def previous_season_id():
    now = int(time.time()) - 7 * 86400
    return time.strftime("%G-W%V", time.localtime(now))

def current_event():
    week = int(time.strftime("%W", time.localtime()))
    events = [
        ("harvest", "🌾 Урожайная неделя", "Сбор урожая приносит на 25% больше 🪙."),
        ("social", "💬 Социальная неделя", "Сообщения дают в 2 раза больше очков сезона."),
        ("bonus", "🎁 Щедрая неделя", "Ежедневный бонус увеличен на 50 🪙."),
    ]
    return events[week % len(events)]

def _quest_for_day(day_key=None):
    day_key = day_key or current_day_key()
    seed = sum(ord(c) for c in day_key)
    quests = [
        ("messages", 20, "💬 Напиши 20 сообщений в группе"),
        ("dice", 3, "🎲 Сыграй в кубы 3 раза"),
        ("harvest", 1, "🌾 Собери урожай хотя бы 1 раз"),
        ("bonus", 1, "🎁 Забери ежедневный бонус"),
    ]
    return quests[seed % len(quests)]

def get_daily_quest(chat_id, user_id):
    day = current_day_key()
    qtype, target, title = _quest_for_day(day)
    cursor.execute("SELECT progress, claimed FROM daily_quests WHERE chat_id=? AND user_id=? AND day_key=?", (chat_id, user_id, day))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO daily_quests(chat_id,user_id,day_key,quest_type,progress,claimed) VALUES(?,?,?,?,0,0)", (chat_id,user_id,day,qtype))
        conn.commit()
        progress, claimed = 0, 0
    else:
        progress, claimed = row
    return {"type": qtype, "target": target, "title": title, "progress": min(progress, target), "claimed": bool(claimed), "day": day}

def progress_daily_quest(chat_id, user_id, quest_type, amount=1):
    q = get_daily_quest(chat_id, user_id)
    if q["type"] != quest_type or q["claimed"]:
        return q, False
    new_progress = min(q["target"], q["progress"] + amount)
    cursor.execute("UPDATE daily_quests SET progress=? WHERE chat_id=? AND user_id=? AND day_key=?", (new_progress,chat_id,user_id,q["day"]))
    conn.commit()
    q["progress"] = new_progress
    completed = new_progress >= q["target"]
    return q, completed

def claim_daily_quest(chat_id, user_id):
    q = get_daily_quest(chat_id, user_id)
    if q["claimed"]:
        return False, q, get_coins(chat_id,user_id), get_sapy(user_id)
    if q["progress"] < q["target"]:
        return False, q, get_coins(chat_id,user_id), get_sapy(user_id)
    cursor.execute("UPDATE daily_quests SET claimed=1 WHERE chat_id=? AND user_id=? AND day_key=?", (chat_id,user_id,q["day"]))
    conn.commit()
    coins = add_coins(chat_id,user_id,50)
    sapy = add_sapy(user_id,5)
    return True, q, coins, sapy

def is_global_season_enabled():
    cursor.execute("SELECT enabled FROM global_season_config WHERE id=1")
    row = cursor.fetchone()
    return bool(row and row[0])

def get_global_season_config():
    cursor.execute("SELECT season_name, rewards_json FROM global_season_config WHERE id=1")
    row = cursor.fetchone() or ("", "")
    return row[0] or "", row[1] or ""

def get_global_season_settings(season_id=None):
    season_id = season_id or current_season_id()
    cursor.execute("SELECT season_name, rewards_json FROM global_season_settings WHERE season_id=?", (season_id,))
    row = cursor.fetchone()
    if row:
        return row[0] or "", row[1] or ""
    return get_global_season_config()

def set_global_season_config(season_name=None, rewards_json=None, season_id=None):
    current_name, current_rewards = get_global_season_config()
    name = current_name if season_name is None else season_name.strip()
    rewards = current_rewards if rewards_json is None else rewards_json
    cursor.execute("UPDATE global_season_config SET season_name=?, rewards_json=? WHERE id=1", (name, rewards))
    sid = season_id or current_season_id()
    cursor.execute("INSERT INTO global_season_settings(season_id,season_name,rewards_json) VALUES(?,?,?) ON CONFLICT(season_id) DO UPDATE SET season_name=excluded.season_name,rewards_json=excluded.rewards_json", (sid, name, rewards))
    conn.commit()
    return name, rewards

def set_global_season(enabled):
    enabled = bool(enabled)
    if enabled:
        # Зафиксировать настройки именно для текущей недели перед включением.
        name, rewards = get_global_season_config()
        cursor.execute("INSERT INTO global_season_settings(season_id,season_name,rewards_json) VALUES(?,?,?) ON CONFLICT(season_id) DO NOTHING", (current_season_id(), name, rewards))
    cursor.execute("UPDATE global_season_config SET enabled=? WHERE id=1", (1 if enabled else 0,))
    conn.commit()
    return enabled

def toggle_global_season():
    return set_global_season(not is_global_season_enabled())

def admin_sapy_week_key(ts=None):
    return time.strftime("%Y-W%W", time.localtime(ts or time.time()))

def admin_sapy_weekly_used(admin_id):
    cursor.execute("SELECT amount FROM admin_sapy_weekly WHERE admin_id=? AND week_key=?", (admin_id, admin_sapy_week_key()))
    row = cursor.fetchone()
    return int(row[0]) if row else 0

def admin_sapy_weekly_remaining(admin_id, limit=300):
    return max(0, int(limit) - admin_sapy_weekly_used(admin_id))

def admin_add_sapy_limited(admin_id, user_id, amount, weekly_limit=300):
    amount = int(amount)
    if amount <= 0:
        return False, admin_sapy_weekly_used(admin_id), get_sapy(user_id)
    used = admin_sapy_weekly_used(admin_id)
    if used + amount > weekly_limit:
        return False, used, get_sapy(user_id)
    balance = add_sapy(user_id, amount)
    week = admin_sapy_week_key()
    cursor.execute("INSERT INTO admin_sapy_weekly(admin_id,week_key,amount) VALUES(?,?,?) ON CONFLICT(admin_id,week_key) DO UPDATE SET amount=amount+excluded.amount", (admin_id, week, amount))
    conn.commit()
    return True, used + amount, balance

def season_scope(chat_id):
    return 0 if is_global_season_enabled() else chat_id

def add_season_points(chat_id, user_id, points):
    season = current_season_id()
    # Локальный рейтинг сохраняем всегда — это позволяет безопасно вернуть
    # групповые сезоны после выключения глобального режима.
    cursor.execute("""INSERT INTO season_points(season_id,chat_id,user_id,points) VALUES(?,?,?,?)
    ON CONFLICT(season_id,chat_id,user_id) DO UPDATE SET points=points+excluded.points""", (season,chat_id,user_id,points))
    if is_global_season_enabled():
        cursor.execute("""INSERT INTO global_season_points(season_id,user_id,points) VALUES(?,?,?)
        ON CONFLICT(season_id,user_id) DO UPDATE SET points=points+excluded.points""", (season,user_id,points))
    conn.commit()
    return get_season_points(chat_id,user_id)

def get_season_points(chat_id,user_id,season_id=None):
    season_id = season_id or current_season_id()
    if is_global_season_enabled():
        cursor.execute("SELECT points FROM global_season_points WHERE season_id=? AND user_id=?", (season_id,user_id))
    else:
        cursor.execute("SELECT points FROM season_points WHERE season_id=? AND chat_id=? AND user_id=?", (season_id,chat_id,user_id))
    row=cursor.fetchone()
    return row[0] if row else 0

def get_season_top(chat_id, season_id=None, limit=10):
    season_id = season_id or current_season_id()
    if is_global_season_enabled():
        cursor.execute("""SELECT user_id, points FROM global_season_points WHERE season_id=? ORDER BY points DESC, user_id ASC LIMIT ?""", (season_id,limit))
    else:
        cursor.execute("""SELECT user_id, points FROM season_points WHERE season_id=? AND chat_id=? ORDER BY points DESC, user_id ASC LIMIT ?""", (season_id,chat_id,limit))
    return cursor.fetchall()

def _latest_user_name(user_id):
    cursor.execute("SELECT user_name FROM reputation WHERE user_id=? AND user_name IS NOT NULL AND user_name!='' ORDER BY rowid DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 'Игрок'

def get_season_top_named(chat_id, season_id=None, limit=10):
    """Топ сезона вместе с сохранённым никнеймом/именем.
    Возвращает (user_id, user_name, points). В глобальном режиме рейтинг
    объединяет очки игрока из всех групп.
    """
    season_id = season_id or current_season_id()
    if is_global_season_enabled():
        cursor.execute("""SELECT user_id, points FROM global_season_points
                         WHERE season_id=? ORDER BY points DESC, user_id ASC LIMIT ?""", (season_id,limit))
        rows = cursor.fetchall()
        return [(uid, _latest_user_name(uid), points) for uid, points in rows]
    cursor.execute("""
        SELECT s.user_id, COALESCE(NULLIF(r.user_name, ''), 'Игрок'), s.points
        FROM season_points s
        LEFT JOIN reputation r ON r.chat_id = s.chat_id AND r.user_id = s.user_id
        WHERE s.season_id=? AND s.chat_id=?
        ORDER BY s.points DESC, s.user_id ASC
        LIMIT ?
    """, (season_id, chat_id, limit))
    return cursor.fetchall()

def get_global_reward_rows(season_id=None):
    """Возвращает кастомные награды глобального сезона как список (from,to,coins,sapy)."""
    import json
    _name, raw = get_global_season_settings(season_id or previous_season_id())
    if not raw:
        return []
    try:
        rows = json.loads(raw)
        return [tuple(map(int, row)) for row in rows if len(row) == 4]
    except Exception:
        return []

def claim_previous_season_rewards(chat_id, user_id):
    season = previous_season_id()
    scope = season_scope(chat_id)
    top = get_season_top(chat_id, season, 50)
    place = next((i+1 for i,(uid,_) in enumerate(top) if uid == user_id), None)
    if not place:
        return False, None, 0, get_sapy(user_id)
    cursor.execute("SELECT claimed FROM season_rewards WHERE season_id=? AND chat_id=? AND user_id=?", (season,scope,user_id))
    row=cursor.fetchone()
    if row and row[0]:
        return False, place, 0, get_sapy(user_id)

    custom_rows = get_global_reward_rows(season) if is_global_season_enabled() else []
    if custom_rows:
        reward = next(((coins, sapy) for start, end, coins, sapy in custom_rows if start <= place <= end), None)
        if reward is None:
            return False, place, 0, get_sapy(user_id)
        coins, sapy = reward
    else:
        rewards = {
            1:(1000,100), 2:(750,75), 3:(500,50),
            4:(350,35), 5:(350,35),
            6:(250,25), 7:(250,25), 8:(250,25), 9:(250,25), 10:(250,25),
            **{i:(175,15) for i in range(11,21)},
            **{i:(125,10) for i in range(21,31)},
            **{i:(75,7) for i in range(31,41)},
            **{i:(50,5) for i in range(41,51)},
        }
        coins, sapy = rewards[place]
    cursor.execute("INSERT OR REPLACE INTO season_rewards(season_id,chat_id,user_id,place,claimed) VALUES(?,?,?,?,1)", (season,scope,user_id,place))

    # Памятное достижение для топ-3. Не заменяет обычный купленный титул.
    season_title = None
    season_titles = {
        1: "👑 Император сезона",
        2: "🦅 Властелин высоты",
        3: "🐉 Золотой дракон",
        4: "⚡ Громовержец",
        5: "🔥 Пламя сезона",
        6: "💎 Алмазный игрок",
        7: "🌌 Хранитель звёзд",
        8: "🐺 Серый волк",
        9: "🦊 Хитрый лис",
        10: "🏹 Охотник за топом",
        11: "🛡️ Страж рейтинга",
        12: "🌪️ Ураган активности",
        13: "🧭 Покоритель вершин",
        14: "🪐 Звёздный странник",
        15: "🗡️ Дуэлянт сезона",
        16: "🏰 Лорд арены",
        17: "🪽 Вестник победы",
        18: "🧿 Хранитель удачи",
        19: "🏅 Мастер сезона",
        20: "🎯 Меткий претендент",
        21: "⭐ Элита сезона",
        22: "🔥 Вершитель рейтинга",
        23: "💠 Сапфировый игрок",
        24: "🌙 Ночной чемпион",
        25: "☄️ Комета сезона",
        26: "🎖️ Почётный претендент",
        27: "🦊 Серебряный охотник",
        28: "🐲 Дракон арены",
        29: "⚔️ Воин рейтинга",
        30: "🏆 Тридцатка лучших",
        31: "🌟 Яркий игрок",
        32: "🚀 Ракета сезона",
        33: "🧨 Динамит активности",
        34: "🧊 Ледяной стратег",
        35: "🌋 Вулкан чата",
        36: "🎲 Игрок удачи",
        37: "🕶️ Тёмная лошадка",
        38: "🔮 Провидец рейтинга",
        39: "🦾 Железный игрок",
        40: "🎮 Ветеран сезона",
        41: "🏹 Охотник за очками",
        42: "💫 Звёздный боец",
        43: "🪄 Маг активности",
        44: "🌊 Волна сезона",
        45: "🗿 Столп чата",
        46: "🎯 Меткий участник",
        47: "🛡️ Надёжный боец",
        48: "✨ Искра сезона",
        49: "🏃 Быстрый претендент",
        50: "🎖️ Финалист сезона",
    }
    if place in season_titles:
        season_title = f"{season_titles[place]} #{season.split('-W')[-1]}"
    if season_title:
        cursor.execute("INSERT OR REPLACE INTO season_achievements(season_id,chat_id,user_id,place,title) VALUES(?,?,?,?,?)", (season,scope,user_id,place,season_title))
        grant_title(user_id, season_title, equip=False)

    conn.commit()
    coins_total=add_coins(chat_id,user_id,coins)
    sapy_total=add_sapy(user_id,sapy)
    return True, place, coins, sapy_total

def get_season_achievements(user_id):
    cursor.execute("SELECT season_id, place, title FROM season_achievements WHERE user_id=? ORDER BY season_id DESC", (user_id,))
    return cursor.fetchall()

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

def touch_activity(user_id, chat_id=0, count_message=False):
    now = int(time.time())
    cursor.execute("""
    INSERT INTO user_activity (user_id, last_seen, last_chat_id, message_count)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        last_seen = excluded.last_seen,
        last_chat_id = excluded.last_chat_id,
        message_count = user_activity.message_count + excluded.message_count
    """, (user_id, now, chat_id, 1 if count_message else 0))
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



def get_user_messages(chat_id, user_id):
    cursor.execute("SELECT messages_all FROM reputation WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    row = cursor.fetchone()
    return row[0] if row else 0

def get_user_dice_score(chat_id, user_id):
    cursor.execute("SELECT dice_score FROM reputation WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    row = cursor.fetchone()
    return row[0] if row else 0

def get_first_seen(user_id):
    cursor.execute("SELECT first_seen FROM user_meta WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

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
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        user_id INTEGER,
        achievement_id TEXT,
        title TEXT,
        description TEXT,
        rarity INTEGER DEFAULT 1,
        awarded_at INTEGER NOT NULL,
        PRIMARY KEY (user_id, achievement_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_awards (
        chat_id INTEGER,
        award_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        to_user_id INTEGER,
        name TEXT,
        description TEXT,
        rarity INTEGER DEFAULT 1,
        created_at INTEGER NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_titles (
        user_id INTEGER,
        title TEXT,
        PRIMARY KEY (user_id, title)
    )
    """)
    try:
        cursor.execute("ALTER TABLE user_cosmetics ADD COLUMN nickname TEXT")
    except sqlite3.OperationalError:
        pass
    # Переносим уже купленные старые титулы в коллекцию титулов.
    cursor.execute("INSERT OR IGNORE INTO user_titles(user_id, title) SELECT user_id, title FROM user_cosmetics WHERE title IS NOT NULL AND title != ''")
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
        grant_title(user_id, title, equip=True)
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
    return row[0] if row and row[0] else None


def get_user_titles(user_id):
    cursor.execute("SELECT title FROM user_titles WHERE user_id = ? ORDER BY title", (user_id,))
    return [row[0] for row in cursor.fetchall()]


def grant_title(user_id, title, equip=False):
    title = (title or "").strip()
    if not title:
        return False
    cursor.execute("INSERT OR IGNORE INTO user_titles(user_id, title) VALUES (?, ?)", (user_id, title))
    if equip:
        cursor.execute("INSERT INTO user_cosmetics(user_id, title) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET title=excluded.title", (user_id, title))
    conn.commit()
    return True


def set_user_title(user_id, title):
    titles = get_user_titles(user_id)
    if title not in titles:
        return False
    cursor.execute("INSERT INTO user_cosmetics(user_id, title) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET title=excluded.title", (user_id, title))
    conn.commit()
    return True


def clear_user_title(user_id):
    cursor.execute("INSERT INTO user_cosmetics(user_id, title) VALUES (?, NULL) ON CONFLICT(user_id) DO UPDATE SET title=NULL", (user_id,))
    conn.commit()


def get_custom_nickname(user_id):
    cursor.execute("SELECT nickname FROM user_cosmetics WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row and row[0] else None


def set_custom_nickname(user_id, nickname):
    nickname = (nickname or "").strip()
    cursor.execute("INSERT INTO user_cosmetics(user_id, nickname) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET nickname=excluded.nickname", (user_id, nickname or None))
    conn.commit()


def clear_custom_nickname(user_id):
    cursor.execute("UPDATE user_cosmetics SET nickname=NULL WHERE user_id = ?", (user_id,))
    conn.commit()


def get_display_name(user_id, fallback_name="Игрок"):
    nickname = get_custom_nickname(user_id)
    return nickname or fallback_name or "Игрок"


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


# --- АДМИН-ЦЕНТР SAPRONEM ---
def log_admin_action(chat_id, admin_id, action, target_id=None, amount=0, details=""):
    cursor.execute("INSERT INTO admin_action_log(chat_id,admin_id,action,target_id,amount,details,created_at) VALUES(?,?,?,?,?,?,?)",
                   (chat_id, admin_id, action, target_id, int(amount or 0), details, int(time.time())))
    conn.commit()

def admin_action_log(chat_id, limit=15):
    cursor.execute("SELECT admin_id, action, target_id, amount, details, created_at FROM admin_action_log WHERE chat_id=? ORDER BY id DESC LIMIT ?", (chat_id, limit))
    return cursor.fetchall()

def get_group_settings(chat_id):
    cursor.execute("SELECT farm_enabled,quests_enabled,seasons_enabled,events_enabled,economy_enabled FROM group_settings WHERE chat_id=?", (chat_id,))
    row=cursor.fetchone()
    if not row:
        cursor.execute("INSERT OR IGNORE INTO group_settings(chat_id) VALUES(?)", (chat_id,)); conn.commit()
        return (1,1,1,1,1)
    return row

def set_group_setting(chat_id, key, enabled):
    allowed={"farm_enabled","quests_enabled","seasons_enabled","events_enabled","economy_enabled"}
    if key not in allowed: return False
    cursor.execute(f"INSERT INTO group_settings(chat_id) VALUES(?) ON CONFLICT(chat_id) DO UPDATE SET {key}=excluded.{key}", (chat_id,))
    # The previous statement inserts default values on a missing row, so update separately for existing/missing rows.
    cursor.execute(f"UPDATE group_settings SET {key}=? WHERE chat_id=?", (1 if enabled else 0, chat_id))
    conn.commit(); return True

def admin_group_stats(chat_id):
    cursor.execute("SELECT COUNT(*) FROM reputation WHERE chat_id=?", (chat_id,)); members=cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(messages_all),0) FROM reputation WHERE chat_id=?", (chat_id,)); messages=cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reputation WHERE chat_id=? AND messages_all>0", (chat_id,)); active=cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM farms WHERE user_id IN (SELECT user_id FROM reputation WHERE chat_id=?) AND crop IS NOT NULL", (chat_id,)); farms=cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM season_points WHERE chat_id=? AND season_id=?", (chat_id, current_season_id())); season=cursor.fetchone()[0]
    return {"members":members,"messages":messages,"active":active,"farms":farms,"season_players":season}

def admin_stats():
    now = int(time.time())
    stats = {}
    cursor.execute("SELECT COUNT(*) FROM user_meta")
    stats["users"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM profiles")
    stats["profiles"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM reputation WHERE chat_id < 0")
    stats["groups"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reputation")
    stats["memberships"] = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(messages_all), 0) FROM reputation")
    stats["messages"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_activity WHERE last_seen >= ?", (now - 86400,))
    stats["active_24h"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_activity WHERE last_seen >= ?", (now - 7 * 86400,))
    stats["active_7d"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM user_activity WHERE last_seen > 0")
    stats["tracked"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM premium_wallet")
    stats["wallets"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM premium_wallet WHERE vip_until > ?", (now,))
    stats["vip"] = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(sapy), 0) FROM premium_wallet")
    stats["sapy"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM star_payments")
    stats["payments"] = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(stars), 0) FROM star_payments")
    stats["stars"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM user_meta WHERE referred_by IS NOT NULL")
    stats["referred_users"] = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(messages_all), 0) FROM reputation WHERE chat_id < 0 AND messages_all > 0")
    stats["group_messages"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM daily_quests WHERE claimed = 1 AND day_key = ?", (current_day_key(),))
    stats["quests_today"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM farms WHERE crop IS NOT NULL")
    stats["planted"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM season_points WHERE season_id = ?", (current_season_id(),))
    stats["season_players"] = cursor.fetchone()[0]
    return stats

def admin_top_referrers(limit=10):
    cursor.execute("""
        SELECT u.user_id, COUNT(r.user_id) AS refs
        FROM user_meta u
        JOIN user_meta r ON r.referred_by = u.user_id
        GROUP BY u.user_id
        ORDER BY refs DESC, u.user_id ASC LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def admin_recent_activity(limit=10):
    cursor.execute("""
        SELECT user_id, last_seen, message_count FROM user_activity
        ORDER BY last_seen DESC LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def admin_user(user_id):
    ensure_premium_user(user_id)
    cursor.execute("SELECT name, age, city, bio FROM profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()
    cursor.execute("SELECT sapy, vip_until FROM premium_wallet WHERE user_id = ?", (user_id,))
    premium = cursor.fetchone() or (0, 0)
    cursor.execute("SELECT COUNT(*) FROM user_meta WHERE referred_by = ?", (user_id,))
    referrals = cursor.fetchone()[0]
    return profile, premium, referrals



def admin_grant_title(user_id, title, equip=True):
    ensure_premium_user(user_id)
    return grant_title(user_id, title, equip=equip)



def admin_grant_title(user_id, title, equip=True):
    ensure_premium_user(user_id)
    return grant_title(user_id, title, equip=equip)

def admin_add_sapy(user_id, amount):
    ensure_premium_user(user_id)
    return add_sapy(user_id, amount)

def admin_set_vip_days(user_id, days):
    ensure_premium_user(user_id)
    now = int(time.time())
    current = get_vip_until(user_id)
    base = max(now, current)
    until = base + int(days) * 86400
    cursor.execute("UPDATE premium_wallet SET vip_until = ? WHERE user_id = ?", (until, user_id))
    conn.commit()
    return until

def admin_remove_vip(user_id):
    ensure_premium_user(user_id)
    cursor.execute("UPDATE premium_wallet SET vip_until = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

def admin_payment_history(limit=20):
    cursor.execute("""
        SELECT user_id, stars, sapy, payload, created_at
        FROM star_payments ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def admin_all_user_ids():
    cursor.execute("SELECT user_id FROM user_meta")
    return [row[0] for row in cursor.fetchall()]


# --- ДОСТИЖЕНИЯ И НАГРАДЫ ---
ACHIEVEMENT_DEFS = [
    ("first_message", "💬 Первое слово", "Отправить первое сообщение", 1),
    ("messages_100", "🗣️ Болтун", "100 сообщений", 1),
    ("messages_1000", "📣 Голос чата", "1 000 сообщений", 2),
    ("messages_5000", "🎙️ Легенда чата", "5 000 сообщений", 4),
    ("dice_100", "🎲 Игрок", "100 бросков кубика", 1),
    ("dice_1000", "🎰 Зависимый от удачи", "1 000 бросков кубика", 3),
    ("karma_25", "⭐ Уважаемый", "25 кармы", 2),
    ("karma_100", "🌟 Авторитет", "100 кармы", 4),
    ("ref_3", "👥 Свой человек", "3 реферала", 2),
    ("ref_10", "📢 Агитатор", "10 рефералов", 3),
    ("sapy_500", "💎 Саповый запас", "500 сапов", 2),
    ("sapy_5000", "💎 Магнат", "5 000 сапов", 5),
    ("season_100", "🏆 Претендент", "100 очков сезона", 2),
    ("profile", "👤 В игре", "Создать профиль", 1),
    ("vip", "👑 Премиум", "Получить VIP", 3),
]

def list_achievement_defs():
    return ACHIEVEMENT_DEFS

def get_achievements(user_id):
    cursor.execute("SELECT achievement_id,title,description,rarity,awarded_at FROM achievements WHERE user_id=? ORDER BY rarity DESC, awarded_at DESC", (user_id,))
    return cursor.fetchall()

def has_achievement(user_id, achievement_id):
    cursor.execute("SELECT 1 FROM achievements WHERE user_id=? AND achievement_id=?", (user_id, achievement_id))
    return cursor.fetchone() is not None

def grant_achievement(user_id, achievement_id):
    row = next((x for x in ACHIEVEMENT_DEFS if x[0] == achievement_id), None)
    if not row or has_achievement(user_id, achievement_id):
        return False, row
    _, title, desc, rarity = row
    cursor.execute("INSERT INTO achievements(user_id,achievement_id,title,description,rarity,awarded_at) VALUES(?,?,?,?,?,?)", (user_id,achievement_id,title,desc,rarity,int(time.time())))
    conn.commit()
    return True, row

def evaluate_achievements(user_id, chat_id=0):
    checks = []
    if chat_id:
        msgs = get_user_messages(chat_id,user_id)
        dice = get_user_dice_score(chat_id,user_id)
        karma = get_karma(chat_id,user_id)
        season = get_season_points(chat_id,user_id)
        if msgs >= 1: checks.append("first_message")
        if msgs >= 100: checks.append("messages_100")
        if msgs >= 1000: checks.append("messages_1000")
        if msgs >= 5000: checks.append("messages_5000")
        if dice >= 100: checks.append("dice_100")
        if dice >= 1000: checks.append("dice_1000")
        if karma >= 25: checks.append("karma_25")
        if karma >= 100: checks.append("karma_100")
        if season >= 100: checks.append("season_100")
    if get_referral_count(user_id) >= 3: checks.append("ref_3")
    if get_referral_count(user_id) >= 10: checks.append("ref_10")
    if get_sapy(user_id) >= 500: checks.append("sapy_500")
    if get_sapy(user_id) >= 5000: checks.append("sapy_5000")
    if get_profile(user_id): checks.append("profile")
    if vip_seconds_left(user_id) > 0: checks.append("vip")
    newly=[]
    for aid in checks:
        ok,row=grant_achievement(user_id,aid)
        if ok: newly.append(row)
    return newly

def add_group_award(chat_id, from_user_id, to_user_id, name, description, rarity):
    cursor.execute("INSERT INTO group_awards(chat_id,from_user_id,to_user_id,name,description,rarity,created_at) VALUES(?,?,?,?,?,?,?)", (chat_id,from_user_id,to_user_id,name,description,int(rarity),int(time.time())))
    conn.commit()
    return cursor.lastrowid

def get_group_awards(chat_id, user_id, limit=50):
    cursor.execute("SELECT award_id,from_user_id,name,description,rarity,created_at FROM group_awards WHERE chat_id=? AND to_user_id=? ORDER BY created_at DESC LIMIT ?", (chat_id,user_id,limit))
    return cursor.fetchall()

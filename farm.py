import time
import database as db

# --- НАСТРОЙКА КУЛЬТУР ---
# cost — цена семян (списывается сразу при посадке)
# time — сколько секунд растёт культура
# reward — сколько монет даёт при сборе урожая
CROPS = {
    "морковь":   {"cost": 10, "time": 5 * 60,  "reward": 25,  "emoji": "🥕"},
    "картофель": {"cost": 20, "time": 15 * 60, "reward": 55,  "emoji": "🥔"},
    "пшеница":   {"cost": 40, "time": 30 * 60, "reward": 110, "emoji": "🌾"},
    "арбуз":     {"cost": 80, "time": 60 * 60, "reward": 240, "emoji": "🍉"},
}


def format_time_left(seconds: int) -> str:
    if seconds <= 0:
        return "готово!"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes} мин {secs} сек"
    return f"{secs} сек"


def build_farm_text(chat_id: int, user_id: int) -> str:
    plots = db.get_farm(chat_id, user_id)
    coins = db.get_coins(chat_id, user_id)

    lines = [f"🌱 <b>Твоя ферма</b> | Монеты: <b>{coins}</b> 🪙\n"]

    for plot_number, crop, planted_at in plots:
        if crop is None:
            lines.append(f"Грядка {plot_number}: пусто, можно сажать")
            continue

        info = CROPS.get(crop)
        if info is None:
            lines.append(f"Грядка {plot_number}: неизвестная культура ⚠️")
            continue

        elapsed = int(time.time()) - planted_at
        left = info["time"] - elapsed

        if left <= 0:
            lines.append(f"Грядка {plot_number}: {info['emoji']} {crop} — готово к сбору! ✅")
        else:
            lines.append(f"Грядка {plot_number}: {info['emoji']} {crop} — созреет через {format_time_left(left)}")

    lines.append("\nКоманды: <code>посадить культура</code>, <code>собрать</code>")
    lines.append("Культуры: " + ", ".join(f"{v['emoji']} {k} ({v['cost']}🪙)" for k, v in CROPS.items()))
    return "\n".join(lines)


def plant(chat_id: int, user_id: int, crop: str):
    """Возвращает (успех: bool, текст ответа: str)"""
    crop = crop.strip().lower()
    if crop not in CROPS:
        return False, f"Такой культуры нет. Доступно: {', '.join(CROPS.keys())}"

    info = CROPS[crop]
    plots = db.get_farm(chat_id, user_id)
    free_plot = next((p for p, c, _ in plots if c is None), None)

    if free_plot is None:
        return False, "Все грядки заняты! Дождись урожая и собери его командой <code>собрать</code> 🌾"

    coins = db.get_coins(chat_id, user_id)
    if coins < info["cost"]:
        return False, f"Не хватает монет. Нужно {info['cost']}🪙, у тебя {coins}🪙"

    db.add_coins(chat_id, user_id, -info["cost"])
    db.plant_crop(chat_id, user_id, free_plot, crop)
    return True, (
        f"{info['emoji']} Посадил <b>{crop}</b> на грядку {free_plot}. "
        f"Созреет через {format_time_left(info['time'])}."
    )


def harvest(chat_id: int, user_id: int, reward_multiplier: float = 1.0):
    """Возвращает (собрал_ли_что-то: bool, текст ответа: str)"""
    plots = db.get_farm(chat_id, user_id)
    collected = []
    total_reward = 0
    now = int(time.time())

    for plot_number, crop, planted_at in plots:
        if crop is None:
            continue
        info = CROPS.get(crop)
        if info is None:
            continue
        if now - planted_at >= info["time"]:
            reward = int(info["reward"] * reward_multiplier)
            total_reward += reward
            collected.append(f"{info['emoji']} {crop} (+{reward}🪙)")
            db.clear_plot(chat_id, user_id, plot_number)

    if not collected:
        return False, "Собирать пока нечего — ничего не созрело."

    db.add_coins(chat_id, user_id, total_reward)
    text = "Собрал урожай:\n" + "\n".join(collected) + f"\n\nВсего получено: <b>{total_reward}</b>🪙"
    return True, text

import html
import database as db

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def mention(user_id: int, name: str) -> str:
    display = db.get_display_name(user_id, name)
    title = db.get_user_title(user_id)
    label = f"{title} · {display}" if title else display
    return f'<a href="tg://user?id={user_id}">{html.escape(label)}</a>'


def build_top_messages_text(chat_id: int) -> str:
    rows = db.get_top_messages(chat_id, limit=10)
    if not rows:
        return "Чат пока пуст! 💬"

    lines = ["<b>📊 Топ по количеству сообщений:</b>\n"]
    for i, (user_id, user_name, count) in enumerate(rows, start=1):
        place = MEDALS.get(i, f"{i}.")
        lines.append(f"{place} {mention(user_id, user_name)} — <b>{count}</b> соо")
    return "\n".join(lines)


def build_top_dice_text(chat_id: int) -> str:
    rows = db.get_top_dice(chat_id, limit=10)
    if not rows:
        return "🎲 В кубы в этом чате еще никто не играл!"

    lines = ["<b>🏆 Топ везунчиков чата по кубам:</b>\n"]
    for i, (user_id, user_name, total_score) in enumerate(rows, start=1):
        place = MEDALS.get(i, f"{i}.")
        display = db.get_display_name(user_id, user_name)
        title = db.get_user_title(user_id)
        label = f"{title} · {display}" if title else display
        lines.append(f"{place} <b>{label}</b> — {total_score} очков 🎲")
    return "\n".join(lines)

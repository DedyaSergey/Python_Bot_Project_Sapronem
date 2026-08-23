from html import escape

import database as db

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{escape(name)}</a>'


def build_top_messages_text(chat_id: int) -> str:
    rows = db.get_top_messages(chat_id, limit=10)
    if not rows:
        return "<b>📊 Топ активности</b>\n\nПока здесь тихо. Напиши первое сообщение! 💬"

    lines = [
        "<b>📊 Топ активности</b>",
        "<i>Самые разговорчивые участники чата</i>",
        "",
    ]
    for i, (user_id, user_name, count) in enumerate(rows, start=1):
        place = MEDALS.get(i, f"{i}.")
        lines.append(f"{place}  {mention(user_id, user_name)}  ·  <b>{count}</b> сообщ.")
    return "\n".join(lines)


def build_top_dice_text(chat_id: int) -> str:
    rows = db.get_top_dice(chat_id, limit=10)
    if not rows:
        return "<b>🎲 Топ Удачи</b>\n\nПока никто не бросал кубы. Испытай удачу первым!"

    lines = [
        "<b>🎲 Топ удачи</b>",
        "<i>Лучшие результаты бросков в этом чате</i>",
        "",
    ]
    for i, (user_name, total_score) in enumerate(rows, start=1):
        place = MEDALS.get(i, f"{i}.")
        lines.append(f"{place}  <b>{escape(user_name)}</b>  ·  <b>{total_score}</b> очков")
    return "\n".join(lines)

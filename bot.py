import asyncio
import time
import random
import logging
import html
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import database
import rp
import rights
import farm
import top

# Логи ошибок будут видны во вкладке "Deployments -> Logs" на Railway.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

DICE_COOLDOWN = {}
PROPOSED_MARRIAGES = {}

# ID владельца/админов задаётся в Railway Variables:
# ADMIN_IDS=123456789,987654321
def load_admin_ids():
    raw = os.getenv("ADMIN_IDS", "")
    result = set()
    for value in raw.replace(";", ",").split(","):
        value = value.strip()
        if value.isdigit():
            result.add(int(value))
    return result

ADMIN_IDS = load_admin_ids()

def is_owner(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
         InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_analytics")],
        [InlineKeyboardButton(text="👤 Пользователь", callback_data="admin_user")],
        [InlineKeyboardButton(text="💎 Выдать сапы", callback_data="admin_add_sapy"),
         InlineKeyboardButton(text="➖ Забрать сапы", callback_data="admin_remove_sapy")],
        [InlineKeyboardButton(text="👑 Выдать VIP", callback_data="admin_add_vip"),
         InlineKeyboardButton(text="❌ Снять VIP", callback_data="admin_remove_vip")],
        [InlineKeyboardButton(text="🏷️ Выдать титул", callback_data="admin_add_title"),
         InlineKeyboardButton(text="✏️ Сменить ник", callback_data="admin_nickname")],
        [InlineKeyboardButton(text="💳 Платежи", callback_data="admin_payments"),
         InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔄 Обновить ID админов", callback_data="admin_reload")],
    ])

class AdminForm(StatesGroup):
    USER_ID = State()
    SAPY_ACTION = State()
    SAPY_AMOUNT = State()
    VIP_USER = State()
    VIP_DAYS = State()
    TITLE_ACTION = State()
    NICKNAME_ACTION = State()
    BROADCAST = State()

# Покупка сапов за Telegram Stars. Цены указаны в Stars (XTR).
STAR_PACKAGES = {
    "50": {"stars": 50, "sapy": 500, "title": "💎 500 сапов"},
    "150": {"stars": 150, "sapy": 1650, "title": "💎 1 650 сапов"},
    "500": {"stars": 500, "sapy": 6000, "title": "💎 6 000 сапов"},
}

class ProfileForm(StatesGroup):
    SET_NAME = State()
    SET_AGE = State()
    SET_CITY = State()
    SET_BIO = State()
    SET_PHOTO = State()

def private_menu(profile_exists=False):
    profile_button = "👤 Мой профиль" if profile_exists else "✨ Создать профиль"
    profile_callback = "menu_profile" if profile_exists else "create_profile"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=profile_button, callback_data=profile_callback),
         InlineKeyboardButton(text="🎮 Как играть", callback_data="menu_help")],
        [InlineKeyboardButton(text="💎 Магазин Sapronem", callback_data="menu_shop")],
        [InlineKeyboardButton(text="👑 Sapronem VIP", callback_data="menu_vip")],
        [InlineKeyboardButton(text="🎁 Пригласить друзей", callback_data="menu_ref")],
        [InlineKeyboardButton(text="➕ Добавить в группу", url="https://t.me/Sapronem_Bot?startgroup=true")],
    ])


def group_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌱 Ферма", callback_data="group_farm"), InlineKeyboardButton(text="🎁 Бонус", callback_data="group_bonus")],
        [InlineKeyboardButton(text="🏆 Топ", callback_data="group_top"), InlineKeyboardButton(text="📜 Задание", callback_data="group_quest")],
        [InlineKeyboardButton(text="👑 Сезон", callback_data="group_season"), InlineKeyboardButton(text="🎉 Событие", callback_data="group_event")],
        [InlineKeyboardButton(text="❓ Команды", callback_data="group_help")],
    ])



@dp.message(Command("admin"), F.chat.type == "private")
async def admin_command(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    await state.clear()
    await message.answer("🔐 <b>Панель владельца Sapronem</b>\n\nВыбери действие:", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_reload")
async def admin_reload(callback: types.CallbackQuery):
    global ADMIN_IDS
    ADMIN_IDS = load_admin_ids()
    if not is_owner(callback.from_user.id):
        await callback.answer("❌ Нет доступа.", show_alert=True)
        return
    await callback.answer("✅ Список админов обновлён.", show_alert=True)

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: types.CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("❌ Нет доступа.", show_alert=True)
        return
    action = callback.data
    await callback.answer()
    if action == "admin_stats":
        s = database.admin_stats()
        await callback.message.answer(
            "📊 <b>Статистика Sapronem</b>\n\n"
            f"👤 Пользователи: <b>{s['users']}</b>\n"
            f"📝 Профили: <b>{s['profiles']}</b>\n"
            f"👥 Группы: <b>{s['groups']}</b>\n"
            f"💬 Сообщения: <b>{s['messages']}</b>\n"
            f"🔥 Активных за 24ч: <b>{s['active_24h']}</b>\n"
            f"📅 Активных за 7д: <b>{s['active_7d']}</b>\n"
            f"💎 Сапов в кошельках: <b>{s['sapy']}</b>\n"
            f"👑 Активных VIP: <b>{s['vip']}</b>\n"
            f"💳 Платежей Stars: <b>{s['payments']}</b>\n"
            f"⭐ Получено Stars: <b>{s['stars']}</b>"
        )
    elif action == "admin_analytics":
        s = database.admin_stats()
        refs = database.admin_top_referrers(5)
        ref_lines = []
        for i, (uid, count) in enumerate(refs, 1):
            ref_lines.append(f"{i}. <code>{uid}</code> — {count} приглаш.")
        ref_text = "\n".join(ref_lines) if ref_lines else "Пока нет рефералов."
        conversion = (s['profiles'] / s['users'] * 100) if s['users'] else 0
        avg_msgs = (s['messages'] / s['memberships']) if s['memberships'] else 0
        await callback.message.answer(
            "📈 <b>Аналитика Sapronem</b>\n\n"
            f"🔥 DAU (24ч): <b>{s['active_24h']}</b>\n"
            f"📅 WAU (7д): <b>{s['active_7d']}</b>\n"
            f"👤 Всего пользователей: <b>{s['users']}</b>\n"
            f"📝 Создали профиль: <b>{s['profiles']}</b> ({conversion:.1f}%)\n"
            f"👥 Групп: <b>{s['groups']}</b>\n"
            f"💬 Всего сообщений: <b>{s['messages']}</b>\n"
            f"📊 В среднем сообщений на участника чатов: <b>{avg_msgs:.1f}</b>\n"
            f"🎯 Игроков в текущем сезоне: <b>{s['season_players']}</b>\n"
            f"📜 Заданий забрано сегодня: <b>{s['quests_today']}</b>\n"
            f"🌱 Посаженных культур сейчас: <b>{s['planted']}</b>\n"
            f"👥 Пришли по рефералам: <b>{s['referred_users']}</b>\n\n"
            "🏆 <b>Топ рефереров</b>\n" + ref_text + "\n\n"
            f"💎 Сапов в экономике: <b>{s['sapy']}</b>\n"
            f"👑 Активных VIP: <b>{s['vip']}</b>\n"
            f"⭐ Stars получено: <b>{s['stars']}</b>"
        )
    elif action == "admin_user":
        await state.set_state(AdminForm.USER_ID)
        await callback.message.answer("👤 Введи Telegram ID пользователя:")
    elif action in ("admin_add_sapy", "admin_remove_sapy"):
        await state.update_data(sapy_sign=1 if action == "admin_add_sapy" else -1)
        await state.set_state(AdminForm.SAPY_ACTION)
        await callback.message.answer("💎 Введи через пробел: <code>ID пользователя количество</code>\nНапример: <code>123456789 500</code>")
    elif action == "admin_add_vip":
        await state.set_state(AdminForm.VIP_USER)
        await state.update_data(vip_action="add")
        await callback.message.answer("👑 Введи ID пользователя и количество дней:\n<code>123456789 30</code>")
    elif action == "admin_remove_vip":
        await state.set_state(AdminForm.VIP_USER)
        await state.update_data(vip_action="remove")
        await callback.message.answer("❌ Введи Telegram ID пользователя:")
    elif action == "admin_add_title":
        await state.set_state(AdminForm.TITLE_ACTION)
        await callback.message.answer("🏷️ Введи через |: <code>ID | Титул</code>\nНапример: <code>123456789 | 🐉 Дракон</code>\n\nВарианты: 👑 Легенда · 🐉 Дракон · 🔥 Огненный · ⚡ Молния · 🌙 Ночной · 💎 Богатей · 🐺 Волк · 🏆 Чемпион")
    elif action == "admin_nickname":
        await state.set_state(AdminForm.NICKNAME_ACTION)
        await callback.message.answer("✏️ Введи через |: <code>ID | Ник</code>\nЧтобы сбросить ник: <code>ID | -</code>")
    elif action == "admin_payments":
        rows = database.admin_payment_history()
        if not rows:
            await callback.message.answer("💳 Платежей пока нет.")
            return
        lines = ["💳 <b>Последние платежи</b>\n"]
        for uid, stars, sapy, payload, created in rows:
            dt = time.strftime("%d.%m.%Y %H:%M", time.localtime(created))
            lines.append(f"👤 <code>{uid}</code> — ⭐ {stars} → 💎 {sapy} — {dt}")
        await callback.message.answer("\n".join(lines))
    elif action == "admin_broadcast":
        await state.set_state(AdminForm.BROADCAST)
        await callback.message.answer("📢 Отправь текст рассылки одним сообщением.\n\nДля отмены: <code>отмена</code>")

@dp.message(AdminForm.USER_ID, F.chat.type == "private")
async def admin_find_user(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear(); return
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Нужен числовой Telegram ID.")
        return
    uid = int(message.text.strip())
    profile, premium, referrals = database.admin_user(uid)
    name = profile[0] if profile else "нет профиля"
    display_name = database.get_display_name(uid, name)
    title = database.get_user_title(uid)
    vip_until = premium[1]
    vip = time.strftime("%d.%m.%Y %H:%M", time.localtime(vip_until)) if vip_until > int(time.time()) else "нет"
    await state.clear()
    title_line = f"Титул: <b>{html.escape(title)}</b>\n" if title else "Титул: <i>нет</i>\n"
    await message.answer(
        "👤 <b>Пользователь</b>\n\n"
        f"ID: <code>{uid}</code>\n"
        f"Ник: <b>{html.escape(display_name)}</b>\n"
        f"{title_line}"
        f"💎 Сапы: <b>{premium[0]}</b>\n"
        f"👑 VIP до: <b>{vip}</b>\n"
        f"👥 Пригласил: <b>{referrals}</b>"
    )

@dp.message(AdminForm.SAPY_ACTION, F.chat.type == "private")
async def admin_sapy_action(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear(); return
    parts = (message.text or "").split()
    if len(parts) != 2 or not all(x.isdigit() for x in parts):
        await message.answer("❌ Формат: <code>ID количество</code>")
        return
    uid, amount = map(int, parts)
    data = await state.get_data()
    amount *= data.get("sapy_sign", 1)
    balance = database.admin_add_sapy(uid, amount)
    await state.clear()
    await message.answer(f"✅ Баланс <code>{uid}</code> изменён на <b>{amount:+d} 💎</b>.\nТеперь: <b>{balance} 💎</b>")

@dp.message(AdminForm.VIP_USER, F.chat.type == "private")
async def admin_vip_action(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear(); return
    data = await state.get_data()
    parts = (message.text or "").split()
    if data.get("vip_action") == "remove":
        if len(parts) != 1 or not parts[0].isdigit():
            await message.answer("❌ Нужен Telegram ID.")
            return
        uid = int(parts[0])
        database.admin_remove_vip(uid)
        await state.clear()
        await message.answer(f"❌ VIP снят с <code>{uid}</code>.")
        return
    if len(parts) != 2 or not all(x.isdigit() for x in parts):
        await message.answer("❌ Формат: <code>ID дни</code>")
        return
    uid, days = map(int, parts)
    until = database.admin_set_vip_days(uid, days)
    await state.clear()
    await message.answer(f"👑 VIP выдан пользователю <code>{uid}</code> на <b>{days} дней</b>.\nДо: <b>{time.strftime('%d.%m.%Y %H:%M', time.localtime(until))}</b>")

@dp.message(AdminForm.TITLE_ACTION, F.chat.type == "private")
async def admin_title_action(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear(); return
    parts = (message.text or "").split("|", 1)
    if len(parts) != 2 or not parts[0].strip().isdigit() or not parts[1].strip():
        await message.answer("❌ Формат: <code>ID | Титул</code>")
        return
    uid = int(parts[0].strip())
    title = parts[1].strip()
    database.admin_grant_title(uid, title, equip=True)
    await state.clear()
    await message.answer(f"✅ Титул <b>{html.escape(title)}</b> выдан <code>{uid}</code> и установлен.")

@dp.message(AdminForm.NICKNAME_ACTION, F.chat.type == "private")
async def admin_nickname_action(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear(); return
    parts = (message.text or "").split("|", 1)
    if len(parts) != 2 or not parts[0].strip().isdigit():
        await message.answer("❌ Формат: <code>ID | Ник</code>")
        return
    uid = int(parts[0].strip())
    nickname = parts[1].strip()
    if nickname == "-":
        database.clear_custom_nickname(uid)
        result = "сброшен — снова используется имя Telegram"
    else:
        if len(nickname) > 32:
            await message.answer("❌ Ник максимум 32 символа.")
            return
        database.set_custom_nickname(uid, nickname)
        result = f"установлен: <b>{html.escape(nickname)}</b>"
    await state.clear()
    await message.answer(f"✏️ Ник пользователя <code>{uid}</code> {result}.")

@dp.message(AdminForm.BROADCAST, F.chat.type == "private")
async def admin_broadcast(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear(); return
    if (message.text or "").strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Рассылка отменена.")
        return
    text = message.html_text
    user_ids = database.admin_all_user_ids()
    sent = failed = 0
    await message.answer(f"📢 Начинаю рассылку для <b>{len(user_ids)}</b> пользователей...")
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.04)
    await state.clear()
    await message.answer(f"✅ Рассылка завершена.\n\n📨 Отправлено: <b>{sent}</b>\n⚠️ Не доставлено: <b>{failed}</b>", reply_markup=admin_menu())

@dp.pre_checkout_query()
async def pre_checkout_handler(query: types.PreCheckoutQuery):
    payload = query.invoice_payload or ""
    if not payload.startswith("sapy_"):
        await query.answer(ok=False, error_message="Неизвестный товар.")
        return
    key = payload.removeprefix("sapy_")
    pkg = STAR_PACKAGES.get(key)
    if not pkg or query.currency != "XTR" or query.total_amount != pkg["stars"]:
        await query.answer(ok=False, error_message="Параметры заказа не совпадают. Попробуй оформить покупку ещё раз.")
        return
    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payment = message.successful_payment
    payload = payment.invoice_payload or ""
    if not payload.startswith("sapy_") or payment.currency != "XTR":
        return
    key = payload.removeprefix("sapy_")
    pkg = STAR_PACKAGES.get(key)
    if not pkg or payment.total_amount != pkg["stars"]:
        logger.error("Invalid Stars payment payload/amount: user=%s payload=%s amount=%s", message.from_user.id, payload, payment.total_amount)
        await message.answer("❌ Платёж получен, но параметры заказа не совпали. Напиши администратору Sapronem.")
        return
    applied, balance = database.apply_star_payment(
        user_id=message.from_user.id,
        charge_id=payment.telegram_payment_charge_id,
        payload=payload,
        stars=payment.total_amount,
        sapy=pkg["sapy"],
    )
    if applied:
        await message.answer(
            f"✅ <b>Платёж успешно получен!</b>\n\n"
            f"Начислено: <b>+{pkg['sapy']} 💎</b>\n"
            f"Баланс: <b>{balance} 💎</b>\n\n"
            "Спасибо за поддержку Sapronem! 💎"
        )
    else:
        await message.answer(f"ℹ️ Этот платёж уже был обработан. Твой баланс: <b>{balance} 💎</b>.")


@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start_private(message: types.Message, state: FSMContext, command: CommandStart):
    await state.clear()
    referred_by = None
    args = (command.args or "").strip()
    if args.startswith("ref_"):
        try:
            referred_by = int(args[4:])
        except ValueError:
            referred_by = None

    existing_referrer = database.get_referral_inviter(message.from_user.id)
    database.touch_activity(message.from_user.id, message.chat.id)
    saved_referrer = database.register_user(message.from_user.id, referred_by)
    if saved_referrer and existing_referrer is None and saved_referrer != message.from_user.id:
        database.add_sapy(saved_referrer, 10)
        if database.get_referral_count(saved_referrer) >= 3 and not database.get_referral_reward_claimed(saved_referrer):
            database.add_sapy(saved_referrer, 50)
            database.claim_referral_reward(saved_referrer)
    database.ensure_premium_user(message.from_user.id)
    mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a>'
    profile_exists = database.get_profile(message.from_user.id) is not None
    profile_line = "✅ Профиль уже создан." if profile_exists else "👤 Создай профиль — это займёт пару минут."

    text = (
        f"👋 <b>Добро пожаловать в Sapronem, {mention}!</b>\n\n"
        "🎮 <b>Игровой бот для Telegram-групп.</b>\n\n"
        "Здесь можно: \n"
        "⭐ прокачивать репутацию\n"
        "🏆 попадать в топ участников\n"
        "💍 создавать игровые отношения\n"
        "🎲 играть в кубы\n"
        "🌱 развивать свою ферму\n"
        "💬 использовать RP-команды\n\n"
        f"{profile_line}\n\n"
        "Добавь меня в свою группу — и начнём 🚀"
    )
    if saved_referrer and saved_referrer != message.from_user.id:
        text += "\n\n🎉 Ты пришёл по приглашению друга!"
    await message.answer(text, reply_markup=private_menu(profile_exists))


@dp.callback_query(F.data == "create_profile")
async def create_profile_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("📝 <b>Создаём профиль!</b>\n\nНапиши своё имя:")
    await state.set_state(ProfileForm.SET_NAME)
    await callback.answer()


def build_profile_text(target_user, chat_id=0):
    uid = target_user.id
    profile = database.get_profile(uid)
    if not profile:
        return "❌ Профиль ещё не создан.\n\nНапиши <code>заполнить анкету</code> в ЛС боту."

    name, age, city, bio, _photo_id = profile
    username = f"@{target_user.username}" if target_user.username else target_user.full_name
    display_name = database.get_display_name(uid, target_user.full_name)
    vip_left = database.vip_seconds_left(uid)
    if vip_left:
        days = vip_left // 86400
        hours = (vip_left % 86400) // 3600
        vip_line = f"👑 VIP: <b>активен</b> — осталось <b>{days} дн. {hours} ч.</b>"
    else:
        vip_line = "👑 VIP: <b>нет</b>"

    title = database.get_user_title(uid)
    title_line = f"🏷️ Титул: <b>{html.escape(title)}</b>\n" if title else ""
    karma = database.get_karma(chat_id, uid) if chat_id else 0
    messages = database.get_user_messages(chat_id, uid) if chat_id else 0
    dice = database.get_user_dice_score(chat_id, uid) if chat_id else 0
    sapy = database.get_sapy(uid)
    refs = database.get_referral_count(uid)
    first_seen = database.get_first_seen(uid)
    days_in_game = max(1, (int(time.time()) - first_seen) // 86400 + 1) if first_seen else 0

    lines = [
        f"👤 <b>{html.escape(display_name)}</b>",
        f"🔹 {html.escape(username)}",
        f"🪪 Имя профиля: <b>{html.escape(name)}</b>",
        title_line.rstrip(),
        "",
        f"🎂 Возраст: <b>{age}</b>",
        f"🌆 Город: <b>{html.escape(city)}</b>",
        f"📝 {html.escape(bio)}",
        "",
        f"⭐ Карма: <b>{karma}</b>",
        f"💬 Сообщений: <b>{messages}</b>",
        f"🎲 Очки кубов: <b>{dice}</b>",
        f"🏆 Очки сезона: <b>{database.get_season_points(chat_id, uid) if chat_id else 0}</b>",
        "",
        f"💎 Сапы: <b>{sapy}</b>",
        vip_line,
        f"👥 Рефералов: <b>{refs}</b>",
    ]
    if chat_id:
        lines.insert(14, f"🪙 Монеты группы: <b>{database.get_coins(chat_id, uid)}</b>")
    else:
        lines.insert(14, "🪙 Монеты: <i>показываются в группе</i>")
    if days_in_game:
        lines.append(f"📅 В Sapronem: <b>{days_in_game} дн.</b>")
    return "\n".join(x for x in lines if x != "")

@dp.callback_query(F.data == "menu_profile")
async def menu_profile(callback: types.CallbackQuery):
    profile = database.get_profile(callback.from_user.id)
    if not profile:
        await callback.message.answer(
            "👤 <b>Профиль ещё не создан.</b>\n\n"
            "Нажми кнопку <b>✨ Создать профиль</b> в сообщении /start или напиши <code>заполнить анкету</code>."
        )
    else:
        _name, _age, _city, _bio, photo_id = profile
        caption = build_profile_text(callback.from_user, 0)
        if photo_id:
            await callback.message.answer_photo(photo_id, caption=caption)
        else:
            await callback.message.answer(caption)
    await callback.answer()

@dp.callback_query(F.data == "menu_help")
async def menu_help(callback: types.CallbackQuery):
    await callback.message.answer(
        "🎮 <b>Как играть в Sapronem</b>\n\n"
        "1️⃣ Создай профиль.\n"
        "2️⃣ Добавь бота в Telegram-группу.\n"
        "3️⃣ Общайся — бот считает сообщения и репутацию.\n"
        "4️⃣ Играй в кубы, используй RP-команды и создавай отношения.\n"
        "5️⃣ Открой <b>ферму</b>, получай 🪙 монеты и выращивай культуры.\n\n"
        "💡 Чем активнее ваше сообщество, тем интереснее игра."
    )
    await callback.answer()


@dp.callback_query(F.data == "menu_shop")
async def menu_shop(callback: types.CallbackQuery):
    database.ensure_premium_user(callback.from_user.id)
    items = database.get_shop_items()
    lines = ["🛍️ <b>Магазин Sapronem</b>", f"\nТвой баланс: <b>{database.get_sapy(callback.from_user.id)} 💎</b>\n"]
    for item_id, name, description, price, item_type in items:
        lines.append(f"<b>{name}</b> — {price} 💎\n{description}")
    lines.append("\nПокупка: <code>купить ID</code>, например <code>купить title_star</code>.")
    lines.append("🎁 Подарочный набор можно использовать ответом на сообщение друга командой <code>подарить набор</code>.")
    lines.append("\n💳 <b>Пополнить сапы за Telegram Stars:</b>")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{pkg['title']} — {pkg['stars']} ⭐", callback_data=f"buy_stars_{key}")]
        for key, pkg in STAR_PACKAGES.items()
    ])
    await callback.message.answer("\n\n".join(lines), reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_stars_"))
async def buy_stars_callback(callback: types.CallbackQuery):
    if callback.message.chat.type != "private":
        await callback.answer("Покупки сапов доступны в ЛС с ботом.", show_alert=True)
        return
    key = callback.data.removeprefix("buy_stars_")
    pkg = STAR_PACKAGES.get(key)
    if not pkg:
        await callback.answer("Пакет не найден.", show_alert=True)
        return
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=pkg["title"],
        description=f"Пополнение баланса Sapronem на {pkg['sapy']} 💎 сапов.",
        payload=f"sapy_{key}",
        currency="XTR",
        prices=[LabeledPrice(label=pkg["title"], amount=pkg["stars"])],
    )
    await callback.answer()


@dp.callback_query(F.data == "menu_vip")
async def menu_vip(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    database.ensure_premium_user(user_id)
    sapy = database.get_sapy(user_id)
    vip_left = database.vip_seconds_left(user_id)
    if vip_left:
        days = vip_left // 86400
        hours = (vip_left % 86400) // 3600
        status = f"✅ VIP активен ещё <b>{days} дн. {hours} ч.</b>"
    else:
        status = "❌ VIP не активен"
    await callback.message.answer(
        "💎 <b>Sapronem VIP</b>\n\n"
        f"Баланс: <b>{sapy} 💎</b>\n"
        f"{status}\n\n"
        "Что даёт VIP:\n"
        "🌱 +1 дополнительная грядка\n"
        "🎁 +100 🪙 к ежедневному бонусу\n"
        "✨ VIP-статус в профиле\n\n"
        "💎 <b>100 сапов = 30 дней VIP</b>\n"
        "Покупка: <code>купить вип</code>\n"
        "Баланс: <code>сапы</code>"
    )
    await callback.answer()


@dp.callback_query(F.data == "menu_ref")
async def menu_ref_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    database.register_user(user_id)
    database.ensure_premium_user(user_id)
    count = database.get_referral_count(user_id)
    link = f"https://t.me/Sapronem_Bot?start=ref_{user_id}"
    await callback.message.answer(
        f"👥 <b>Приглашай друзей</b>\n\n"
        f"Приглашено: <b>{count}</b>\n\n"
        f"🔗 <code>{link}</code>\n\n"
        "🎁 За каждого нового пользователя: <b>+10 💎</b>\n"
        "🔥 За 3 приглашённых: ещё <b>+50 💎</b>."
    )
    await callback.answer()


@dp.callback_query(F.data == "group_farm")
async def group_farm_callback(callback: types.CallbackQuery):
    if callback.message.chat.type not in ["group", "supergroup"]:
        await callback.answer("Ферма работает в группах", show_alert=True)
        return
    database.ensure_economy_user(callback.message.chat.id, callback.from_user.id)
    await callback.message.answer(farm.build_farm_text(callback.message.chat.id, callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data == "group_bonus")
async def group_bonus_callback(callback: types.CallbackQuery):
    if callback.message.chat.type not in ["group", "supergroup"]:
        await callback.answer("Бонус работает в группах", show_alert=True)
        return
    await send_daily_bonus(callback.message, callback.from_user)
    await callback.answer()


@dp.callback_query(F.data == "group_top")
async def group_top_callback(callback: types.CallbackQuery):
    if callback.message.chat.type not in ["group", "supergroup"]:
        await callback.answer("Топ работает в группах", show_alert=True)
        return
    await callback.message.answer(top.build_top_messages_text(callback.message.chat.id))
    await callback.answer()


@dp.callback_query(F.data == "group_quest")
async def group_quest_callback(callback: types.CallbackQuery):
    if callback.message.chat.type not in ["group", "supergroup"]:
        await callback.answer("Задания работают в группах", show_alert=True); return
    await callback.message.answer(build_daily_quest_text(callback.message.chat.id, callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "group_season")
async def group_season_callback(callback: types.CallbackQuery):
    if callback.message.chat.type not in ["group", "supergroup"]:
        await callback.answer("Сезоны работают в группах", show_alert=True); return
    await callback.message.answer(build_season_text(callback.message.chat.id, callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "group_event")
async def group_event_callback(callback: types.CallbackQuery):
    event_id, title, desc = database.current_event()
    await callback.message.answer(f"🎉 <b>{title}</b>\n\n{desc}\n\nСобытие меняется каждую неделю.")
    await callback.answer()

@dp.callback_query(F.data == "group_help")
async def group_help_callback(callback: types.CallbackQuery):
    await callback.message.answer(
        "📚 <b>Основные команды Sapronem</b>\n\n"
        "🌱 <code>ферма</code> — твоя ферма\n"
        "🎁 <code>бонус</code> — ежедневные монеты\n"
        "🏆 <code>топ весь</code> — топ сообщений\n"
        "📜 <code>задание</code> — ежедневное задание\n"
        "👑 <code>сезон</code> — недельный сезон и награды\n"
        "🎉 <code>событие</code> — текущее событие\n"
        "🎲 <code>кубы</code> / <code>топ кубы</code>\n"
        "👤 <code>профиль</code> — твой профиль (или ответом на сообщение)\n"
        "🏷️ <code>титулы</code> — коллекция титулов\n"
        "✏️ <code>+ник Имя</code> / <code>-ник</code> — изменить ник\n"
        "⭐ <code>карма</code> — репутация\n"
        "💍 <code>брак</code> — предложить брак ответом на сообщение\n"
        "🎭 RP-команды — ответом на сообщение.\n"
        "💎 <code>сапы</code> — глобальная валюта Sapronem\n"
        "🛍️ <code>магазин</code> — магазин за 💎 сапы\n"
        "👑 <code>вип</code> — преимущества VIP"
    )
    await callback.answer()

def build_daily_quest_text(chat_id, user_id):
    q = database.get_daily_quest(chat_id, user_id)
    if q["claimed"]:
        status = "🎁 Награда уже получена сегодня."
    elif q["progress"] >= q["target"]:
        status = "✅ Задание выполнено! Напиши <code>задание забрать</code>."
    else:
        status = f"Прогресс: <b>{q['progress']}/{q['target']}</b>"
    return f"📜 <b>Ежедневное задание</b>\n\n{q['title']}\n{status}\n\n🎁 Награда: <b>50 🪙 + 5 💎</b>"

def build_season_text(chat_id, user_id):
    # Показываем только номер сезона, без технического идентификатора вроде 2026-W34.
    season = database.current_season_id()
    try:
        season_number = int(season.split("-W")[-1])
    except (ValueError, IndexError):
        season_number = season

    top_rows = database.get_season_top_named(chat_id, season, 10)
    lines = [
        f"👑 <b>Сезон #{season_number}</b>",
        "",
        "📈 Очки сезона получаются за активность в группе.",
        "",
    ]

    if not top_rows:
        lines.append("Пока очков нет — стань первым! 🚀")
    else:
        lines.append("🏆 <b>Топ сезона</b>")
        medals = ["🥇", "🥈", "🥉"]
        for i, (_uid, user_name, points) in enumerate(top_rows, 1):
            medal = medals[i - 1] if i <= 3 else f"{i}."
            # Кликабельное упоминание ведёт на профиль Telegram; отображается
            # именно кастомный ник, а при его отсутствии — обычное имя.
            display_name = database.get_display_name(_uid, user_name or "Игрок")
            title = database.get_user_title(_uid)
            label = f"{title} · {display_name}" if title else display_name
            mention = f'<a href="tg://user?id={_uid}">{html.escape(label)}</a>'
            lines.append(f"{medal} <b>{mention}</b> — <b>{points}</b> очк.")

    my_points = database.get_season_points(chat_id, user_id)
    claimed, place, coins, sapy = database.claim_previous_season_rewards(chat_id, user_id)
    if claimed:
        lines.extend(["", f"🎉 Ты занял <b>{place}</b>-е место в прошлом сезоне и получил награду!"])

    lines.extend([
        "",
        f"🎯 <b>Твои очки:</b> {my_points}",
        "",
        "🎁 <b>Награды топ-50 прошлого сезона</b>",
        "",
        "🥇 <b>1 место</b> — 1000 🪙 + 100 💎",
        "🥈 <b>2 место</b> — 750 🪙 + 75 💎",
        "🥉 <b>3 место</b> — 500 🪙 + 50 💎",
        "🏅 <b>4–5 места</b> — 350 🪙 + 35 💎",
        "🏅 <b>6–10 места</b> — 250 🪙 + 25 💎",
        "🎖 <b>11–20 места</b> — 175 🪙 + 15 💎",
        "🎖 <b>21–30 места</b> — 125 🪙 + 10 💎",
        "🎖 <b>31–40 места</b> — 75 🪙 + 7 💎",
        "🎖 <b>41–50 места</b> — 50 🪙 + 5 💎",
    ])
    return "\n".join(lines)

async def send_daily_bonus(message: types.Message, user: types.User):
    chat_id = message.chat.id
    user_id = user.id
    first = database.ensure_economy_user(chat_id, user_id)
    daily_amount = 200 if database.is_vip(user.id) else 100
    event_id, _, _ = database.current_event()
    if event_id == "bonus":
        daily_amount += 50
    claimed, seconds_left = database.claim_daily_bonus(chat_id, user_id, amount=daily_amount)
    if claimed:
        database.progress_daily_quest(chat_id, user_id, "bonus", 1)

    extra = ""

    if first:
        await message.answer("🎉 <b>Стартовый бонус: +100 🪙</b>\n\nТеперь можно открыть <code>ферма</code> и посадить первую культуру!")
        if claimed:
            await message.answer(f"🎁 <b>Ежедневный бонус: +{daily_amount} 🪙</b>" + extra)
        return

    if claimed:
        await message.answer(f"🎁 <b>Ежедневный бонус: +{daily_amount} 🪙</b>" + extra)
        return

    hours = seconds_left // 3600
    minutes = (seconds_left % 3600) // 60
    await message.answer(f"⏳ Бонус уже получен. Следующий будет через <b>{hours} ч {minutes} мин</b>.")


@dp.message(F.text.lower().strip().in_(["пинг", "ping", "/ping"]))
async def cmd_ping(message: types.Message):
    t1 = time.time()
    temp_msg = await message.answer("⏱ <i>Замеряю скорость...</i>")
    ping_ms = round((time.time() - t1) * 1000)
    await temp_msg.edit_text(f"<b>🏓 Понг!</b>\n⏱ Скорость: <code>{ping_ms} мс</code>\n📊 Система: <code>Стабильна</code>")

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    for member in message.new_chat_members:
        if member.id == bot.id:
            await message.answer(
                "🚀 <b>Sapronem подключён!</b>\n\n"
                "Теперь в этой группе доступны рейтинг активности, репутация, ферма, кубы, RP-команды, браки и модерация.\n\n"
                "🌱 Напиши <code>ферма</code>\n"
                "🏆 <code>топ весь</code>\n"
                "🎁 <code>бонус</code>\n"
                "❓ Или нажми кнопку ниже.",
                reply_markup=group_menu(),
            )
            continue
        user_mention = f'<a href="tg://user?id={member.id}">{member.full_name}</a>'
        await message.answer(f"👋 Добро пожаловать, {user_mention}! 🚀")

@dp.message(F.text.lower().strip() == "заполнить анкету")
async def start_profile_form(message: types.Message, state: FSMContext):
    await message.answer("📝 Напишите свое имя:")
    await state.set_state(ProfileForm.SET_NAME)

@dp.message(ProfileForm.SET_NAME)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("⏳ Введите возраст (цифрами):")
    await state.set_state(ProfileForm.SET_AGE)

@dp.message(ProfileForm.SET_AGE)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите возраст только цифрами!")
        return
    age = int(message.text)
    if age < 1 or age > 120:
        await message.answer("❌ Укажи реальный возраст от 1 до 120.")
        return
    await state.update_data(age=age)
    await message.answer("🌆 Ваш город? (Или напишите <code>0</code> для пропуска):")
    await state.set_state(ProfileForm.SET_CITY)

@dp.message(ProfileForm.SET_CITY)
async def process_city(message: types.Message, state: FSMContext):
    city_text = "Не указан" if message.text.strip() == "0" else message.text.strip()
    await state.update_data(city=city_text)
    await message.answer("✍️ Расскажите немного о себе:")
    await state.set_state(ProfileForm.SET_BIO)

@dp.message(ProfileForm.SET_BIO)
async def process_bio(message: types.Message, state: FSMContext):
    bio = message.text.strip()
    if bio == "0":
        bio = "Не указано"
    await state.update_data(bio=bio)
    await message.answer("📸 Отправьте одно фото для анкеты или напишите <code>пропустить</code>:")
    await state.set_state(ProfileForm.SET_PHOTO)

@dp.message(ProfileForm.SET_PHOTO, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    user_data = await state.get_data()
    database.save_profile(message.from_user.id, user_data['name'], user_data['age'], user_data['city'], user_data['bio'], photo_id)
    await state.clear()
    await message.answer("🎉 Анкета сохранена! Напишите слово <code>анкета</code>.")

@dp.message(ProfileForm.SET_PHOTO)
async def process_photo_invalid(message: types.Message, state: FSMContext):
    if message.text and message.text.lower().strip() in ["пропустить", "0"]:
        user_data = await state.get_data()
        database.save_profile(message.from_user.id, user_data['name'], user_data['age'], user_data['city'], user_data['bio'], None)
        await state.clear()
        await message.answer("🎉 <b>Профиль создан!</b>\n\nФото можно добавить позже, обновив анкету.")
        return
    await message.answer("❌ Пожалуйста, отправь фото или напиши <code>пропустить</code>:")

@dp.message(F.text)
async def handle_messages(message: types.Message):
    text = message.text.lower().strip()
    chat_id, user_id = message.chat.id, message.from_user.id
    user_name = database.get_display_name(message.from_user.id, message.from_user.full_name)
    database.touch_activity(user_id, chat_id, count_message=(message.chat.type in ["group", "supergroup"]))

    if message.chat.type in ["group", "supergroup"]:
        database.log_message(chat_id, user_id, user_name)
        event_id, _, _ = database.current_event()
        season_gain = 2 if event_id == "social" else 1
        database.add_season_points(chat_id, user_id, season_gain)
        database.progress_daily_quest(chat_id, user_id, "messages", 1)

    # ВНИМАНИЕ: ниже независимые блоки "if ... return", а не одна большая
    # elif-цепочка. Раньше в середине файла был отдельный блок проверки
    # триггеров, который случайно склеивал все следующие команды в свою
    # elif-цепочку — из-за этого "топ весь", "варны" и "карма" могли
    # перестать нормально проверяться. Независимые if-блоки от этой
    # проблемы не зависят.

    # 1. ИНФА
    if text.startswith(("saproem инфа ", "сапр инфа ", "инфа ")):
        percent = random.randint(0, 100)
        await message.reply(f"🔮 Вероятность составляет: <b>{percent}%</b>")
        return

    # 2. БРАК
    if text == "брак":
        if message.chat.type in ["private"]:
            return
        if not message.reply_to_message:
            await message.reply("Ответь этой командой на сообщение того, с кем хочешь брак! 💍")
            return
        target = message.reply_to_message.from_user
        if target.id == user_id:
            await message.reply("Нельзя жениться на самом себе! К сожалению ❌")
            return
        if database.check_marriage(chat_id, user_id) or database.check_marriage(chat_id, target.id):
            await message.reply("Кто-то из вас уже состоит в браке! 💔")
            return
        target_display = database.get_display_name(target.id, target.full_name)
        target_title = database.get_user_title(target.id)
        target_label = f"{target_title} · {target_display}" if target_title else target_display
        PROPOSED_MARRIAGES[chat_id] = (user_id, user_name, target.id, target_display)
        t_men = f'<a href="tg://user?id={target.id}">{html.escape(target_label)}</a>'
        my_title = database.get_user_title(user_id)
        my_label = f"{my_title} · {user_name}" if my_title else user_name
        f_men = f'<a href="tg://user?id={user_id}">{html.escape(my_label)}</a>'
        await message.answer(f"💍 {t_men}, пользователь {f_men} предлагает вам брак!\nВы должны ответить <code>согласен</code> или <code>отказ</code>.")
        return

    # 3. СОГЛАСИЕ НА БРАК
    if text in ["согласен", "согласна"]:
        if chat_id in PROPOSED_MARRIAGES and PROPOSED_MARRIAGES[chat_id][2] == user_id:
            u1_id, u1_name, u2_id, u2_name = PROPOSED_MARRIAGES[chat_id]
            database.create_marriage(chat_id, u1_id, u1_name, u2_id, u2_name)
            del PROPOSED_MARRIAGES[chat_id]
            u1_display = database.get_display_name(u1_id, u1_name)
            u2_display = database.get_display_name(u2_id, u2_name)
            u1_title = database.get_user_title(u1_id)
            u2_title = database.get_user_title(u2_id)
            u1_label = f"{u1_title} · {u1_display}" if u1_title else u1_display
            u2_label = f"{u2_title} · {u2_display}" if u2_title else u2_display
            u1_men = f'<a href="tg://user?id={u1_id}">{html.escape(u1_label)}</a>'
            u2_men = f'<a href="tg://user?id={u2_id}">{html.escape(u2_label)}</a>'
            await message.answer(f"🎉 Поздравляем! {u2_men} принял предложение о браке!. 👨‍⚖️ С сегодняшнего дня {u1_men} и {u2_men} теперь официально состоят в браке! 🍾❤️")
            return

    # 4. ОТКАЗ ОТ БРАКА
    if text == "отказ":
        if chat_id in PROPOSED_MARRIAGES and PROPOSED_MARRIAGES[chat_id][2] == user_id:
            del PROPOSED_MARRIAGES[chat_id]
            await message.reply("Разбитое сердце... Предложение брака отклонено. 💔")
            return

    # 5. ПРОВЕРКА БРАКА
    if text in ["браки", "мой брак"]:
        pair = database.check_marriage(chat_id, user_id)
        if not pair:
            await message.reply("Ты еще одинок. Напиши <code>брак</code> в ответ кому-то! 📭")
            return
        await message.reply(f"❤️ Твой official брак в этом чате:\n💍 <b>{pair[0]}</b> и <b>{pair[1]}</b>")
        return

    # 6. РАЗВОД
    if text == "развод":
        pair = database.check_marriage(chat_id, user_id)
        if not pair:
            await message.reply("Тебе не с кем разводиться!")
            return
        database.delete_marriage(chat_id, user_id)
        await message.reply(f"💔 Брак между <b>{pair[0]}</b> и <b>{pair[1]}</b> официально расторгнут.")
        return

    # 7. СОЗДАТЬ ТРИГГЕР
    if text.startswith("создать триггер"):
        is_user_admin = await rights.is_admin(bot, chat_id, user_id)
        if not is_user_admin:
            await message.reply("❌ Ошибка!: Создавать или изменять триггеры могут только администраторы группы!")
            return
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            await message.reply("📝 Формат: <code>создать триггер [слово] [текст ответа]</code>")
            return
        keyword = parts[2].lower().strip()
        reply_text = parts[3]
        database.add_trigger(chat_id, keyword, reply_text)
        await message.reply(f"✅ Триггер на слово <b>«{keyword}»</b> успешно создан!")
        return

    # 8. УДАЛИТЬ ТРИГГЕР
    if text.startswith("удалить триггер"):
        is_user_admin = await rights.is_admin(bot, chat_id, user_id)
        if not is_user_admin:
            await message.reply("❌ Отклонено: Вы не являетесь администратором!")
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply("📝 Формат: <code>удалить триггер [слово]</code>")
            return
        keyword = parts[2].lower().strip()
        database.delete_trigger(chat_id, keyword)
        await message.reply(f"🗑 Триггер на слово <b>«{keyword}»</b> удален!")
        return

    # 9. КУБЫ / КУБИК
    if text in ["кубы", "кубик", "куб"]:
        if message.chat.type in ["private"]:
            await message.answer("🎲 Кубы доступны только в группах!")
            return
        current_time = time.time()
        if user_id in DICE_COOLDOWN:
            passed = current_time - DICE_COOLDOWN[user_id]
            if passed < 30:
                left = round(30 - passed)
                await message.reply(f"⏳ Подожди еще {left} секунд.")
                return
        DICE_COOLDOWN[user_id] = current_time
        dice_msg = await message.answer_dice(emoji="🎲")
        score = dice_msg.dice.value
        await asyncio.sleep(2)
        database.update_dice(chat_id, user_id, user_name, score)
        database.add_season_points(chat_id, user_id, 5)
        database.progress_daily_quest(chat_id, user_id, "dice", 1)
        mention = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        await message.reply(f"🎲 {mention}, выпало число <b>{score}</b>!\nСтатистика обновлена.")
        return

    # 10. ТОП КУБЫ
    if text == "топ кубы":
        if message.chat.type in ["private"]:
            return
        await message.answer(top.build_top_dice_text(chat_id))
        return

    # 11. ТИТУЛЫ
    if text in ["титулы", "титул"] or text.startswith("титул "):
        titles = database.get_user_titles(user_id)
        current = database.get_user_title(user_id)
        if text == "титулы" or text == "титул":
            lines = ["🏷️ <b>Твои титулы</b>", ""]
            if current:
                lines.append(f"✨ Сейчас: <b>{html.escape(current)}</b>")
                lines.append("")
            if titles:
                for i, title in enumerate(titles, 1):
                    mark = "✅" if title == current else "▫️"
                    lines.append(f"{mark} <code>{i}</code>. {html.escape(title)}")
                lines.append("")
                lines.append("Чтобы установить: <code>титул 1</code>")
            else:
                lines.append("У тебя пока нет титулов.")
            await message.answer("\n".join(lines))
            return
        arg = text.removeprefix("титул ").strip()
        chosen = None
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(titles):
                chosen = titles[idx]
        else:
            chosen = next((t for t in titles if t.lower() == arg.lower()), None)
        if not chosen:
            await message.answer("❌ Такого титула нет в твоей коллекции. Напиши <code>титулы</code>.")
            return
        database.set_user_title(user_id, chosen)
        await message.answer(f"🏷️ Титул установлен: <b>{html.escape(chosen)}</b>")
        return

    # 11. НИК
    if text.startswith("+ник"):
        nickname = message.text[4:].strip()
        if not nickname:
            await message.answer("✏️ Напиши так: <code>+ник ТвойНик</code>")
            return
        if len(nickname) > 32:
            await message.answer("❌ Ник максимум 32 символа.")
            return
        database.set_custom_nickname(user_id, nickname)
        await message.answer(f"✅ Ник установлен: <b>{html.escape(nickname)}</b>")
        return
    if text == "-ник":
        database.clear_custom_nickname(user_id)
        await message.answer(f"✅ Ник сброшен. Теперь используется имя Telegram: <b>{html.escape(message.from_user.full_name)}</b>")
        return

    # 12. ПРОФИЛЬ
    if text in ["профиль", "мой профиль", "мой профайл", "анкета"]:
        is_reply = bool(message.reply_to_message)
        target = message.reply_to_message.from_user if is_reply else message.from_user
        profile = database.get_profile(target.id)
        if not profile:
            await message.answer("❌ У данного пользователя ещё нет профиля!" if is_reply else "❌ У вас ещё нет профиля! Пропишите <code>заполнить анкету</code> в ЛС.")
            return
        _p_name, _p_age, _p_city, _p_bio, photo_id = profile
        caption = build_profile_text(target, chat_id if message.chat.type != "private" else 0)
        if photo_id:
            try:
                await bot.send_photo(chat_id=chat_id, photo=photo_id, caption=caption)
            except Exception as e:
                logger.exception(f"Ошибка отправки фото профиля (user_id: {target.id}): {e}")
                await message.answer(caption)
        else:
            await message.answer(caption)
        return

    # 12. SAPRONEM: глобальная валюта и VIP
    # 💎 Сапы и VIP общие для пользователя во всех группах.
    if text in ["сапы", "сап", "баланс", "кошелек", "кошелёк", "рюкзак", "инвентарь", "мешок"]:
        database.ensure_premium_user(user_id)
        sapy = database.get_sapy(user_id)
        vip_left = database.vip_seconds_left(user_id)
        vip_status = "👑 VIP активен" if vip_left else "▫️ VIP не активен"
        group_lines = ""
        if message.chat.type != "private":
            coins = database.get_coins(chat_id, user_id)
            season_points = database.get_season_points(chat_id, user_id)
            group_lines = (
                f"🪙 Монеты группы: <b>{coins}</b>\n"
                f"🏆 Очки сезона: <b>{season_points}</b>\n"
            )
        else:
            group_lines = "🪙 Монеты: <i>зависят от группы</i>\n"
        vip_full = (
            f"👑 VIP: <b>активен</b> — {vip_left // 86400} дн. {(vip_left % 86400) // 3600} ч. осталось"
            if vip_left else "👑 VIP: <b>нет</b>"
        )
        await message.answer(
            "🎒 <b>Рюкзак Sapronem</b>\n\n"
            f"💎 Сапы: <b>{sapy}</b>\n"
            f"{group_lines}"
            f"{vip_full}\n\n"
            "🛍️ <code>магазин</code> — предметы и VIP\n"
            "⭐ <code>пополнить сапы</code> — Telegram Stars"
        )
        return

    if text in ["вип", "vip", "магазин", "премиум"]:
        database.ensure_premium_user(user_id)
        sapy = database.get_sapy(user_id)
        vip_left = database.vip_seconds_left(user_id)
        if vip_left:
            days = vip_left // 86400
            hours = (vip_left % 86400) // 3600
            status = f"✅ активен ещё <b>{days} дн. {hours} ч.</b>"
        else:
            status = "❌ не активен"
        await message.answer(
            "💎 <b>Sapronem VIP</b>\n\n"
            f"Твой баланс: <b>{sapy} 💎</b>\n"
            f"Статус: {status}\n\n"
            "VIP на 30 дней — <b>100 💎</b>\n\n"
            "🌱 +1 грядка\n"
            "🎁 +100 🪙 к ежедневному бонусу\n"
            "✨ VIP-статус в профиле\n\n"
            "Купить: <code>купить вип</code>"
        )
        return

    if text in ["купить вип", "купить vip", "вип купить"]:
        ok, balance, until = database.buy_vip(user_id, price=100, days=30)
        if not ok:
            await message.answer(
                f"❌ Не хватает 💎 сапов. Нужно <b>100</b>, у тебя <b>{balance}</b>.\n\n"
                "Приглашай друзей — за каждого нового пользователя начисляется 💎."
            )
            return
        await message.answer(
            "👑 <b>VIP активирован на 30 дней!</b>\n\n"
            "🌱 +1 грядка\n"
            "🎁 +100 🪙 к ежедневному бонусу\n"
            "✨ VIP-статус в профиле\n\n"
            "Спасибо, что развиваешь Sapronem 💎"
        )
        return

    # 12.5. МАГАЗИН И ПРЕМИАЛЬНЫЕ ПРЕДМЕТЫ
    if text in ["магазин", "шоп", "shop"]:
        items = database.get_shop_items()
        lines = ["🛍️ <b>Магазин Sapronem</b>", f"\nБаланс: <b>{database.get_sapy(user_id)} 💎</b>\n"]
        for item_id, name, description, price, item_type in items:
            lines.append(f"<b>{name}</b> — {price} 💎\n{description}\nID: <code>{item_id}</code>")
        lines.append("\nКупить: <code>купить ID</code>")
        lines.append("\n💳 <b>Пополнить сапы за Telegram Stars:</b>")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{pkg['title']} — {pkg['stars']} ⭐", callback_data=f"buy_stars_{key}")]
            for key, pkg in STAR_PACKAGES.items()
        ])
        await message.answer("\n\n".join(lines), reply_markup=keyboard)
        return

    if text.startswith("купить "):
        item_id = text.split(maxsplit=1)[1].strip()
        ok, result, balance = database.buy_shop_item(user_id, item_id)
        if not ok:
            await message.answer(f"❌ {result}")
            return
        await message.answer(f"🛍️ <b>Покупка успешна!</b>\n\n{result}\n\nБаланс: <b>{balance} 💎</b>")
        return

    if text in ["подарить набор", "подарок"]:
        if not message.reply_to_message:
            await message.answer("🎁 Ответь этой командой на сообщение друга, которому хочешь подарить набор.")
            return
        target_id = message.reply_to_message.from_user.id
        ok, result = database.use_gift_pack(user_id, target_id)
        if not ok:
            await message.answer(f"❌ {result}")
            return
        target_name = message.reply_to_message.from_user.full_name
        await message.answer(f"{result}\n\n🎁 Подарок отправлен: <b>{target_name}</b>")
        return

    # 13. ОГРАНИЧЕНИЕ ЛС
    # Всё, что ниже (топ, ферма, варны, модерация, карма, РП, триггеры) —
    # только для групп. Этот блок обязательно должен идти отдельным
    # верхнеуровневым "if" (не elif), иначе он может случайно перехватить
    # часть команд, написанных в группе.
    if message.chat.type in ["private"]:
        await message.answer("🤖 В ЛС пока ограниченный выбор команд. Есть только команды ПИНГ и Заполнить анкету. Добавьте меня в группу для полного функционала бота!")
        return

    # 13. ЕЖЕДНЕВНЫЙ БОНУС
    if text in ["бонус", "ежедневный бонус", "дейлик"]:
        await send_daily_bonus(message, message.from_user)
        return

    if text in ["задание", "задания", "дейлик задание"]:
        await message.answer(build_daily_quest_text(chat_id, user_id))
        return

    if text in ["задание забрать", "забрать задание"]:
        ok, q, coins_total, sapy_total = database.claim_daily_quest(chat_id, user_id)
        if not ok:
            if q["claimed"]:
                await message.answer("🎁 Награда за сегодняшнее задание уже получена.")
            else:
                await message.answer(f"⏳ Задание ещё не выполнено: <b>{q['progress']}/{q['target']}</b>.")
            return
        await message.answer(f"🎉 <b>Ежедневное задание выполнено!</b>\n\n+50 🪙\n+5 💎\n\nБаланс: <b>{sapy_total} 💎</b>")
        return

    if text in ["сезон", "сезоны", "рейтинг сезона"]:
        await message.answer(build_season_text(chat_id, user_id))
        return

    if text in ["событие", "ивент"]:
        event_id, title, desc = database.current_event()
        await message.answer(f"🎉 <b>{title}</b>\n\n{desc}\n\nСобытие меняется каждую неделю.")
        return

    # 13. ТОП ВСЕХ (СООБЩЕНИЯ)
    if text in ["топ весь", "топ вся", "топ соо", "топ сообщений"]:
        await message.answer(top.build_top_messages_text(chat_id))
        return

    # 14. ФЕРМА
    if text == "ферма":
        first = database.ensure_economy_user(chat_id, user_id)
        if first:
            await message.answer(
                "🎉 <b>Добро пожаловать на ферму!</b>\n\n"
                "Тебе начислено <b>100 🪙</b> стартовых монет.\n"
                "Посади первую культуру командой <code>посадить морковь</code>."
            )
        await message.answer(farm.build_farm_text(chat_id, user_id), reply_markup=group_menu())
        return

    # 15. ПОСАДИТЬ
    if text.startswith("посадить"):
        database.ensure_economy_user(chat_id, user_id)
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply(
                "Укажи культуру: <code>посадить морковь</code>\n"
                "Доступно: " + ", ".join(farm.CROPS.keys())
            )
            return
        success, reply_text = farm.plant(chat_id, user_id, parts[1])
        await message.reply(reply_text)
        return

    # 16. СОБРАТЬ
    if text == "собрать":
        database.ensure_economy_user(chat_id, user_id)
        event_id, _, _ = database.current_event()
        multiplier = 1.25 if event_id == "harvest" else 1.0
        success, reply_text = farm.harvest(chat_id, user_id, reward_multiplier=multiplier)
        if success:
            database.progress_daily_quest(chat_id, user_id, "harvest", 1)
            database.add_season_points(chat_id, user_id, 10)
        await message.reply(reply_text)
        return

    # 17. ПРОСМОТР ВАРНОВ
    if text in ["варны", "мои варны", "предупреждения"]:
        is_reply = bool(message.reply_to_message)
        target = message.reply_to_message.from_user if is_reply else message.from_user
        cursor = database.conn.cursor()
        cursor.execute("SELECT warns FROM reputation WHERE chat_id = ? AND user_id = ?", (chat_id, target.id))
        res = cursor.fetchone()
        user_warns = res[0] if res else 0
        target_display = database.get_display_name(target.id, target.full_name)
        target_title = database.get_user_title(target.id)
        target_label = f"{target_title} · {target_display}" if target_title else target_display
        mention = f'<a href="tg://user?id={target.id}">{html.escape(target_label)}</a>'
        await message.answer(f"⚠️ Предупреждения {mention}: <b>{user_warns}/3</b>")
        return

    # 18. БЛОК МОДЕРАЦИИ (БАН, КИК, МУТ)
    cmd_prefixes = ("бан", "/ban", "кик", "/kick", "мут", "размут", "разбан", "варн", "пред", "снять варны")
    if text.startswith(cmd_prefixes):
        is_user_admin = await rights.is_admin(bot, chat_id, user_id)
        if not is_user_admin:
            await message.reply("❌ Отклонено: Вы не админ!")
            return
        if not message.reply_to_message:
            await message.answer("Ответите этой командой на сообщение!")
            return
        target = message.reply_to_message.from_user
        target_display = database.get_display_name(target.id, target.full_name)
        target_title = database.get_user_title(target.id)
        target_label = f"{target_title} · {target_display}" if target_title else target_display
        t_mention = f'<a href="tg://user?id={target.id}">{html.escape(target_label)}</a>'
        try:
            if text.startswith(("бан", "/ban")):
                await bot.ban_chat_member(chat_id, target.id)
                await message.answer(f"🔨 Пользователь {t_mention} был забанен!")
            elif text.startswith("разбан"):
                await bot.unban_chat_member(chat_id, target.id, only_if_banned=True)
                await message.answer(f"🔓 Пользователь {t_mention} был разбанен!")
            elif text.startswith(("кик", "/kick")):
                await bot.ban_chat_member(chat_id, target.id)
                await bot.unban_chat_member(chat_id, target.id)
                await message.answer(f"🏃 Пользователь {t_mention} был кикнут!")
            elif text.startswith(("варн", "пред")):
                current_warns = database.add_warn(chat_id, target.id)
                if current_warns >= 3:
                    await bot.ban_chat_member(chat_id, target.id)
                    database.reset_warns(chat_id, target.id)
                    await message.answer(f"🔨 {t_mention} получил 3/3 Предупреждений и был забанен!")
                else:
                    await message.answer(f"⚠️ Варн {t_mention}! Всего: <b>{current_warns}/3</b>")
            elif text.startswith("снять варны"):
                database.reset_warns(chat_id, target.id)
                await message.answer(f"✅ С пользователя {t_mention} сняты все варны!")
            elif text.startswith("размут"):
                await bot.restrict_chat_member(
                    chat_id=chat_id, user_id=target.id,
                    permissions=types.ChatPermissions(
                        can_send_messages=True, can_send_audios=True, can_send_documents=True,
                        can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                        can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                        can_add_web_page_previews=True
                    )
                )
                await message.answer(f"🔊 Пользователь {t_mention} размучен!")
            elif text.startswith("мут"):
                parts = message.text.split(maxsplit=2)
                duration_str = "5м"
                reason = ""
                if len(parts) > 1: duration_str = parts[1].lower()
                if len(parts) > 2: reason = parts[2]
                seconds = 300
                if duration_str.endswith(("м", "m")): seconds = int(duration_str[:-1]) * 60
                elif duration_str.endswith(("ч", "h")): seconds = int(duration_str[:-1]) * 3600
                elif duration_str.endswith(("д", "d")): seconds = int(duration_str[:-1]) * 86400
                elif duration_str.isdigit(): seconds = int(duration_str) * 60
                until_date = int(time.time() + seconds)
                await bot.restrict_chat_member(chat_id=chat_id, user_id=target.id, permissions=types.ChatPermissions(can_send_messages=False), until_date=until_date)
                reply_msg = f"🔇 Пользователь {t_mention} замучен на <b>{duration_str}</b>."
                if reason: reply_msg += f"\n📄 Причина: {reason}"
                await message.answer(reply_msg)
        except Exception as e:
            logger.exception(f"Ошибка модерации (команда: {text!r}, chat_id: {chat_id}): {e}")
            await message.answer(f"❌ Ошибка. Проверьте права админа у бота.")
        return

    # 19. СТАТИСТИКА КАРМЫ
    if text in ["+", "плюс", "спасибо", "-", "минус", "карма", "стата"]:
        if text in ["карма", "стата"]:
            target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
            val = database.get_karma(chat_id, target.id)
            await message.answer(f"Репутация {html.escape(database.get_display_name(target.id, target.full_name))}: <b>{val}</b> очков. 🏆")
            return
        if not message.reply_to_message: return
        target = message.reply_to_message.from_user
        if target.id == user_id:
            await message.answer("Нельзя изменять карму самому себе! ❌")
            return
        change = 1 if text in ["+", "плюс", "спасибо"] else -1
        new_val = database.update_karma(chat_id, target.id, change)
        await message.answer(f"📊 Карма пользователя {html.escape(database.get_display_name(target.id, target.full_name))} изменена!\nТекущая карма: <b>{new_val}</b>")
        return

    # 20. РП КОМАНДЫ
    rp_action = rp.check_rp(message.text)
    if rp_action:
        if not message.reply_to_message:
            await message.answer("РП-команды пишутся в ответ на сообщение! 📋")
            return
        target = message.reply_to_message.from_user
        emoji, act = rp_action
        my_title = database.get_user_title(user_id)
        my_label = f"{my_title} · {user_name}" if my_title else user_name
        target_display = database.get_display_name(target.id, target.full_name)
        target_title = database.get_user_title(target.id)
        target_label = f"{target_title} · {target_display}" if target_title else target_display
        f_men = f'<a href="tg://user?id={user_id}">{html.escape(my_label)}</a>'
        t_men = f'<a href="tg://user?id={target.id}">{html.escape(target_label)}</a>'
        await message.answer(f"{emoji} {f_men} {act} {t_men}")
        return

    # 21. ПРОВЕРКА ОБЫЧНЫХ ТРИГГЕРОВ (единственная проверка, в самом конце —
    # чтобы кастомные триггеры не перекрывали встроенные команды выше)
    trigger_reply = database.get_trigger(chat_id, text)
    if trigger_reply:
        await message.answer(trigger_reply)
        return

async def main():
    database.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот успешно запущен в модульном режиме!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

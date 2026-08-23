import asyncio
import time
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import database
import rp
import rights
import farm
import top

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

DICE_COOLDOWN = {}
PROPOSED_MARRIAGES = {}

class ProfileForm(StatesGroup):
    SET_NAME = State()
    SET_AGE = State()
    SET_CITY = State()
    SET_BIO = State()
    SET_PHOTO = State()

@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start_private(message: types.Message):
    mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a>'
    await message.answer(
        f"👋 Привет, {mention}!\n\n"
        f"📝 Напишите <code>заполнить анкету</code>, чтобы создать свой профиль.\n"
        f"👤 Напишите <code>анкета</code>, чтобы посмотреть её.\n\n"
        f"В группах я считаю топ сообщений, репутацию и считываю РП команды!"
    )

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
            continue
        user_mention = f'<a href="tg://user?id={member.id}">{member.full_name}</a>'
        await message.answer(f"Добро пожаловать! {user_mention} 🚀")

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
    await state.update_data(age=int(message.text))
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
    await state.update_data(bio=message.text)
    await message.answer("📸 Отправьте одно фото для анкеты:")
    await state.set_state(ProfileForm.SET_PHOTO)

@dp.message(ProfileForm.SET_PHOTO, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    user_data = await state.get_data()
    database.save_profile(message.from_user.id, user_data['name'], user_data['age'], user_data['city'], user_data['bio'], photo_id)
    await state.clear()
    await message.answer("🎉 Анкета сохранена! Напишите слово <code>анкета</code>.")

@dp.message(ProfileForm.SET_PHOTO)
async def process_photo_invalid(message: types.Message):
    await message.answer("❌ Пожалуйста, отправь именно фото:")

@dp.message(F.text)
async def handle_messages(message: types.Message):
    text = message.text.lower().strip()
    chat_id, user_id, user_name = message.chat.id, message.from_user.id, message.from_user.full_name

    if message.chat.type in ["group", "supergroup"]:
        database.log_message(chat_id, user_id, user_name)

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
        PROPOSED_MARRIAGES[chat_id] = (user_id, user_name, target.id, target.full_name)
        t_men = f'<a href="tg://user?id={target.id}">{target.full_name}</a>'
        f_men = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        await message.answer(f"💍 {t_men}, пользователь {f_men} предлагает вам брак!\nВы должны ответить <code>согласен</code> или <code>отказ</code>.")
        return

    # 3. СОГЛАСИЕ НА БРАК
    if text in ["согласен", "согласна"]:
        if chat_id in PROPOSED_MARRIAGES and PROPOSED_MARRIAGES[chat_id][2] == user_id:
            u1_id, u1_name, u2_id, u2_name = PROPOSED_MARRIAGES[chat_id]
            database.create_marriage(chat_id, u1_id, u1_name, u2_id, u2_name)
            del PROPOSED_MARRIAGES[chat_id]
            u1_men = f'<a href="tg://user?id={u1_id}">{u1_name}</a>'
            u2_men = f'<a href="tg://user?id={u2_id}">{u2_name}</a>'
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
        mention = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        await message.reply(f"🎲 {mention}, выпало число <b>{score}</b>!\nСтатистика обновлена.")
        return

    # 10. ТОП КУБЫ
    if text == "топ кубы":
        if message.chat.type in ["private"]:
            return
        await message.answer(top.build_top_dice_text(chat_id))
        return

    # 11. АНКЕТА
    if text == "анкета":
        is_reply = bool(message.reply_to_message)
        target = message.reply_to_message.from_user if is_reply else message.from_user
        profile = database.get_profile(target.id)
        if not profile:
            await message.answer("❌ У данного пользователя еще нет анкеты!" if is_reply else "❌ У вас еще нет анкеты! Пропишите <code>заполнить анкету</code> в ЛС.")
            return
        p_name, p_age, p_city, p_bio, p_photo_id = profile
        mention = f'<a href="tg://user?id={target.id}">{target.full_name}</a>'
        caption = f"<b>👤 Анкета {mention}:</b>\n\n<b>Имя:</b> {p_name}\n<b>Возраст:</b> {p_age}\n<b>Город:</b> {p_city}\n<b>О себе:</b> {p_bio}"
        try: await bot.send_photo(chat_id=chat_id, photo=p_photo_id, caption=caption)
        except Exception: await message.answer(caption + "\n\n<i>(Ошибка фото)</i>")
        return

    # 12. ОГРАНИЧЕНИЕ ЛС
    # Всё, что ниже (топ, ферма, варны, модерация, карма, РП, триггеры) —
    # только для групп. Этот блок обязательно должен идти отдельным
    # верхнеуровневым "if" (не elif), иначе он может случайно перехватить
    # часть команд, написанных в группе.
    if message.chat.type in ["private"]:
        await message.answer("🤖 В ЛС пока ограниченный выбор команд. Есть только команды ПИНГ и Заполнить анкету. Добавьте меня в группу для полного функционала бота!")
        return

    # 13. ТОП ВСЕХ (СООБЩЕНИЯ)
    if text in ["топ весь", "топ вся", "топ соо", "топ сообщений"]:
        await message.answer(top.build_top_messages_text(chat_id))
        return

    # 14. ФЕРМА
    if text == "ферма":
        await message.answer(farm.build_farm_text(chat_id, user_id))
        return

    # 15. ПОСАДИТЬ
    if text.startswith("посадить"):
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
        success, reply_text = farm.harvest(chat_id, user_id)
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
        mention = f'<a href="tg://user?id={target.id}">{target.full_name}</a>'
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
        t_mention = f'<a href="tg://user?id={target.id}">{target.full_name}</a>'
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
        except Exception:
            await message.answer(f"❌ Ошибка. Проверьте права админа у бота.")
        return

    # 19. СТАТИСТИКА КАРМЫ
    if text in ["+", "плюс", "спасибо", "-", "минус", "карма", "стата"]:
        if text in ["карма", "стата"]:
            target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
            val = database.get_karma(chat_id, target.id)
            await message.answer(f"Репутация {target.full_name}: <b>{val}</b> очков. 🏆")
            return
        if not message.reply_to_message: return
        target = message.reply_to_message.from_user
        if target.id == user_id:
            await message.answer("Нельзя изменять карму самому себе! ❌")
            return
        change = 1 if text in ["+", "плюс", "спасибо"] else -1
        new_val = database.update_karma(chat_id, target.id, change)
        await message.answer(f"📊 Карма пользователя {target.full_name} изменена!\nТекущая карма: <b>{new_val}</b>")
        return

    # 20. РП КОМАНДЫ
    rp_action = rp.check_rp(message.text)
    if rp_action:
        if not message.reply_to_message:
            await message.answer("РП-команды пишутся в ответ на сообщение! 📋")
            return
        target = message.reply_to_message.from_user
        emoji, act = rp_action
        f_men = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        t_men = f'<a href="tg://user?id={target.id}">{target.full_name}</a>'
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

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sapronem_support")

TOKEN = os.getenv("SUPPORT_TOKEN")

def load_ids():
    raw = os.getenv("SUPPORT_ADMIN_IDS", "")
    out = set()
    for value in raw.replace(";", ",").split(","):
        value = value.strip()
        if value.isdigit():
            out.add(int(value))
    return out

ADMIN_IDS = load_ids()
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Связывает ID сообщения у админа с пользователем поддержки.
# Для обычного общения этого достаточно; после перезапуска старые обращения
# лучше начать новым сообщением.
admin_message_users: dict[int, int] = {}


def support_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать в поддержку", callback_data="support_start")],
    ])


@dp.message(CommandStart(), F.chat.type == "private")
async def start(message: types.Message):
    await message.answer(
        "🛟 <b>Поддержка Sapronem</b>\n\n"
        "Есть вопрос, ошибка или предложение? Напиши сообщение сюда.\n\n"
        "📨 Мы передадим его разработчику и ответим прямо в этом чате.\n\n"
        "Пожалуйста, опиши проблему как можно подробнее и, если есть ошибка, приложи скриншот.",
        reply_markup=support_menu(),
    )


@dp.callback_query(F.data == "support_start")
async def support_start(callback: types.CallbackQuery):
    await callback.message.answer(
        "✉️ <b>Напиши сообщение следующим сообщением.</b>\n\n"
        "Можно отправить текст, фото, видео, документ или скриншот."
    )
    await callback.answer()


@dp.message(F.chat.type == "private")
async def user_message(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        return

    user = message.from_user
    header = (
        "🆘 <b>Новое обращение</b>\n"
        f"👤 {user.full_name}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"🔗 @{user.username}" if user.username else
        "🆘 <b>Новое обращение</b>\n"
        f"👤 {user.full_name}\n"
        f"🆔 <code>{user.id}</code>"
    )

    for admin_id in ADMIN_IDS:
        try:
            notice = await bot.send_message(admin_id, header)
            copied = await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            admin_message_users[copied.message_id] = user.id
            await bot.send_message(admin_id, "↩️ Ответь <b>на сообщение выше</b>, чтобы отправить ответ пользователю.")
        except Exception:
            logger.exception("Не удалось передать обращение админу %s", admin_id)

    await message.answer("✅ Сообщение отправлено в поддержку. Ответ придёт сюда.")


@dp.message(F.chat.type == "private", F.reply_to_message)
async def admin_reply(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    target_id = admin_message_users.get(message.reply_to_message.message_id)
    if not target_id:
        await message.answer("⚠️ Не нашёл пользователя для этого обращения. Ответь именно на пересланное сообщение пользователя.")
        return

    try:
        await bot.copy_message(
            chat_id=target_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer("✅ Ответ отправлен.")
    except Exception:
        logger.exception("Не удалось отправить ответ пользователю %s", target_id)
        await message.answer("❌ Не удалось отправить ответ. Возможно, пользователь заблокировал бота.")


async def main():
    if not TOKEN:
        raise RuntimeError("SUPPORT_TOKEN не задан")
    if not ADMIN_IDS:
        raise RuntimeError("SUPPORT_ADMIN_IDS не задан")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

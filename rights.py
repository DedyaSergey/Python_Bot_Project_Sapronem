from aiogram import Bot

async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if member.status in ["creator", "administrator"]:
            return True
    except Exception:
        pass
    return False

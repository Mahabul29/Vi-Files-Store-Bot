from pyrogram import filters
from bot import Bot
from config import ADMINS, USER_REPLY_TEXT


@Bot.on_message(filters.private & filters.incoming & ~filters.user(ADMINS) & ~filters.regex(r"^/"))
async def useless(client, message):
    await message.reply_text(USER_REPLY_TEXT, quote=True)

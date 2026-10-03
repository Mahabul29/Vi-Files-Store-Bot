from pyrogram import filters

from bot import Bot
from config import USER_REPLY_TEXT
from helper_func import admins
from state import in_state


@Bot.on_message(
    filters.private & filters.incoming & ~admins & ~in_state("") & ~filters.regex(r"^/")
)
async def useless(client, message):
    await message.reply_text(USER_REPLY_TEXT, quote=True)

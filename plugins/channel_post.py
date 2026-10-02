import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from config import CHANNEL_ID
from helper_func import encode


@Bot.on_message(filters.channel & filters.incoming & filters.chat(CHANNEL_ID))
async def new_post(client, message):
    string = f"get-{message.id * abs(CHANNEL_ID)}"
    link = f"https://t.me/{client.username}?start={await encode(string)}"
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("ðŸ” Share URL", url=f"https://telegram.me/share/url?url={link}")]]
    )
    try:
        await message.edit_reply_markup(markup)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.edit_reply_markup(markup)
    except Exception:
        pass

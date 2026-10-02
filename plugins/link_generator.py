from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from config import ADMINS, CHANNEL_ID
from helper_func import encode, get_message_id

STATE = {}  # admin_id -> {"mode": ..., "first": ...}


async def _has_state(_, __, m):
    return bool(m.from_user) and m.from_user.id in STATE


has_state = filters.create(_has_state)


async def _send_link(client, message, string):
    link = f"https://t.me/{client.username}?start={await encode(string)}"
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("ðŸ” Share URL", url=f"https://telegram.me/share/url?url={link}")]]
    )
    await message.reply_text(
        f"<b>Here is your link:</b>\n\n{link}",
        quote=True, disable_web_page_preview=True, reply_markup=markup,
    )


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("genlink"))
async def genlink(client, message):
    STATE[message.from_user.id] = {"mode": "single"}
    await message.reply_text(
        "Forward the message from the DB channel (with quotes) or send its post link.\n/cancel to abort."
    )


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("batch"))
async def batch(client, message):
    STATE[message.from_user.id] = {"mode": "first"}
    await message.reply_text(
        "Forward the <b>first</b> message from the DB channel (with quotes) or send its link.\n/cancel to abort."
    )


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("cancel"))
async def cancel(client, message):
    STATE.pop(message.from_user.id, None)
    await message.reply_text("Cancelled.")


@Bot.on_message(filters.private & filters.user(ADMINS) & has_state & ~filters.regex(r"^/"), group=1)
async def collect(client, message):
    uid = message.from_user.id
    st = STATE[uid]
    msg_id = await get_message_id(client, message)
    if not msg_id:
        return await message.reply_text(
            "âŒ That isn't from the DB channel. Forward again or /cancel.", quote=True
        )
    abs_ch = abs(CHANNEL_ID)
    if st["mode"] == "single":
        STATE.pop(uid, None)
        await _send_link(client, message, f"get-{msg_id * abs_ch}")
    elif st["mode"] == "first":
        st.update(mode="last", first=msg_id)
        await message.reply_text("Now forward the <b>last</b> message (or send its link).", quote=True)
    else:
        first = st["first"]
        STATE.pop(uid, None)
        await _send_link(client, message, f"get-{first * abs_ch}-{msg_id * abs_ch}")

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from helper_func import admins, encode, get_message_id
from state import STATE, in_state


def _key(client, message):
    return (client.bot_id, message.from_user.id)


async def _send_link(client, message, string):
    link = f"https://t.me/{client.username}?start={await encode(string)}"
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("ðŸ” Share URL", url=f"https://telegram.me/share/url?url={link}")]]
    )
    await message.reply_text(
        f"<b>Here is your link:</b>\n\n{link}",
        quote=True, disable_web_page_preview=True, reply_markup=markup,
    )


@Bot.on_message(filters.private & admins & filters.command("genlink"))
async def genlink(client, message):
    if not client.cfg["db_channel"]:
        return await message.reply_text("âš ï¸ Set the DB channel first.")
    STATE[_key(client, message)] = {"mode": "lg_single"}
    await message.reply_text(
        "Forward the message from the DB channel (with quotes) or send its post link.\n/cancel to abort."
    )


@Bot.on_message(filters.private & admins & filters.command("batch"))
async def batch(client, message):
    if not client.cfg["db_channel"]:
        return await message.reply_text("âš ï¸ Set the DB channel first.")
    STATE[_key(client, message)] = {"mode": "lg_first"}
    await message.reply_text(
        "Forward the <b>first</b> message from the DB channel (with quotes) or send its link.\n/cancel to abort."
    )


@Bot.on_message(filters.private & filters.command("cancel"))
async def cancel(client, message):
    if STATE.pop(_key(client, message), None) is not None:
        await message.reply_text("Cancelled.")


@Bot.on_message(filters.private & admins & in_state("lg_") & ~filters.regex(r"^/"), group=1)
async def collect(client, message):
    key = _key(client, message)
    st = STATE[key]
    msg_id = await get_message_id(client, message)
    if not msg_id:
        return await message.reply_text(
            "âŒ That isn't from the DB channel. Forward again or /cancel.", quote=True
        )
    abs_ch = abs(client.cfg["db_channel"])
    if st["mode"] == "lg_single":
        STATE.pop(key, None)
        await _send_link(client, message, f"get-{msg_id * abs_ch}")
    elif st["mode"] == "lg_first":
        st.update(mode="lg_last", first=msg_id)
        await message.reply_text("Now forward the <b>last</b> message (or send its link).", quote=True)
    else:
        first = st["first"]
        STATE.pop(key, None)
        await _send_link(client, message, f"get-{first * abs_ch}-{msg_id * abs_ch}")

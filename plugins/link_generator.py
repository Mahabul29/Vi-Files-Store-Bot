from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from database.database import db
from helper_func import admins, encode, get_message_id
from state import STATE, in_state

MEDIA = (
    filters.document | filters.video | filters.audio | filters.photo
    | filters.voice | filters.animation | filters.video_note | filters.sticker
)


def _key(client, message):
    return (client.bot_id, message.from_user.id)


async def _can_store(_, client, m):
    if not m.from_user:
        return False
    st = STATE.get((client.bot_id, m.from_user.id))
    return st is None or st["mode"] == "lg_collect"


can_store = filters.create(_can_store)


async def _send_link(client, message, string):
    link = f"https://t.me/{client.username}?start={await encode(string)}"
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔁 Share URL", url=f"https://telegram.me/share/url?url={link}")]]
    )
    await message.reply_text(
        f"<b>Here is your link:</b>\n\n{link}",
        quote=True, disable_web_page_preview=True, reply_markup=markup,
    )


def _ready(client):
    return bool(client.cfg["db_channel"] and client.db_channel)


NOT_READY = ("⚠️ DB channel isn't available. Make sure this bot is admin (post rights) "
             "in the DB channel.")


# ---------- store files sent by admins/owner into the DB channel ----------

@Bot.on_message(filters.private & admins & MEDIA & can_store & ~filters.regex(r"^/"))
async def store(client, message):
    if not _ready(client):
        return await message.reply_text(NOT_READY, quote=True)
    ch = client.cfg["db_channel"]
    try:
        copied = await message.copy(ch)
    except Exception as e:
        return await message.reply_text(f"❌ Couldn't store: <code>{e}</code>", quote=True)
    await db.add_file(client.bot_id, copied.id)

    st = STATE.get(_key(client, message))
    if st:  # batch collect mode
        st["ids"].append(copied.id)
        return await message.reply_text(f"✅ Added ({len(st['ids'])}). Send more or /done.", quote=True)
    await _send_link(client, message, f"get-{copied.id * abs(ch)}")


# ---------- link commands ----------

@Bot.on_message(filters.private & admins & filters.command("genlink"))
async def genlink(client, message):
    if not _ready(client):
        return await message.reply_text(NOT_READY)
    STATE[_key(client, message)] = {"mode": "lg_single"}
    await message.reply_text(
        "Forward the message from the DB channel (with quotes) or send its post link.\n/cancel to abort."
    )


@Bot.on_message(filters.private & admins & filters.command("batch"))
async def batch(client, message):
    if not _ready(client):
        return await message.reply_text(NOT_READY)
    if client.is_clone:
        STATE[_key(client, message)] = {"mode": "lg_collect", "ids": []}
        return await message.reply_text(
            "Send the files for this batch, then send /done.\n/cancel to abort."
        )
    STATE[_key(client, message)] = {"mode": "lg_first"}
    await message.reply_text(
        "Forward the <b>first</b> message from the DB channel (with quotes) or send its link.\n/cancel to abort."
    )


@Bot.on_message(filters.private & admins & filters.command("done"))
async def done(client, message):
    key = _key(client, message)
    st = STATE.get(key)
    if not st or st["mode"] != "lg_collect":
        return await message.reply_text("No batch in progress. Start one with /batch.")
    STATE.pop(key, None)
    ids = st["ids"]
    if not ids:
        return await message.reply_text("❌ You didn't send any files.")
    abs_ch = abs(client.cfg["db_channel"])
    if len(ids) == 1:
        return await _send_link(client, message, f"get-{ids[0] * abs_ch}")
    await _send_link(client, message, f"get-{min(ids) * abs_ch}-{max(ids) * abs_ch}")


@Bot.on_message(filters.private & filters.command("cancel"))
async def cancel(client, message):
    if STATE.pop(_key(client, message), None) is not None:
        await message.reply_text("Cancelled.")


@Bot.on_message(filters.private & admins & in_state("lg_") & ~filters.regex(r"^/"), group=1)
async def collect(client, message):
    key = _key(client, message)
    st = STATE[key]
    if st["mode"] == "lg_collect":
        if message.media:
            return  # handled by store()
        return await message.reply_text("Send files (not text), or /done to finish.", quote=True)

    msg_id = await get_message_id(client, message)
    if not msg_id:
        return await message.reply_text(
            "❌ That isn't from the DB channel. Forward again or /cancel.", quote=True
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
        

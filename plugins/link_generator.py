from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import asyncio
import os

from bot import Bot, MAIN
from config import CHANNEL_ID, LOGGER
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
        [[InlineKeyboardButton("\U0001f501 𝚂𝚑𝚊𝚛𝚎 𝚄𝚁𝙻", url=f"https://telegram.me/share/url?url={link}")]]
    )
    await message.reply_text(
        f"<b>𝙷𝚎𝚛𝚎 𝚒𝚜 𝚢𝚘𝚞𝚛 𝚕𝚒𝚗𝚔:</b>\n\n{link}",
        quote=True, disable_web_page_preview=True, reply_markup=markup,
    )


def _ready(client):
    if client.is_clone:  # clones store through the main bot
        return True
    return bool(client.cfg["db_channel"] and client.db_channel)


NOT_READY = ("\u26a0\ufe0f 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚒𝚜𝚗'𝚝 𝚊𝚟𝚊𝚒𝚕𝚊𝚋𝚕𝚎. 𝙼𝚊𝚔𝚎 𝚜𝚞𝚛𝚎 𝚝𝚑𝚒𝚜 𝚋𝚘𝚝 𝚒𝚜 𝚊𝚍𝚖𝚒𝚗 (𝚙𝚘𝚜𝚝 𝚛𝚒𝚐𝚑𝚝𝚜) "
             "𝚒𝚗 𝚝𝚑𝚎 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕.")


# ---------- store files sent by admins/owner into the DB channel ----------

ARCHIVE_SEM = asyncio.Semaphore(2)
MAX_ARCHIVE = 2000 * 1024 * 1024  # Telegram bots can't download files above ~2GB


async def _archive(client, message, file_no, caption, media):
    """Background: copy a clone's file into the main DB channel via the main bot."""
    main = MAIN.get("bot")
    if not main or not main.db_channel:
        return
    if (getattr(media, "file_size", 0) or 0) > MAX_ARCHIVE:
        LOGGER.info(f"[{client.username}] file #{file_no} too big to archive (link still works).")
        return
    async with ARCHIVE_SEM:
        path = None
        try:
            path = await client.download_media(message)
            sent = await main.send_document(CHANNEL_ID, path, caption=caption)
            await db.set_archive(client.bot_id, file_no, sent.id)
        except Exception as e:
            LOGGER.warning(f"[{client.username}] archive of file #{file_no} failed: {e}")
        finally:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass


@Bot.on_message(filters.private & admins & MEDIA & can_store & ~filters.regex(r"^/"))
async def store(client, message):
    if not _ready(client):
        return await message.reply_text(NOT_READY, quote=True)
    ch = client.cfg["db_channel"]
    caption = message.caption.html if message.caption else ""

    if client.is_clone:
        # Instant: link uses the clone's own file_id; archiving to the main channel runs in background
        media = getattr(message, message.media.value)
        new_id = await db.next_file_id(client.bot_id)
        await db.add_file(client.bot_id, new_id, media.file_id, caption)
        asyncio.create_task(_archive(client, message, new_id, caption, media))
    else:
        try:
            copied = await message.copy(ch)
        except Exception as e:
            return await message.reply_text(f"\u274c 𝙲𝚘𝚞𝚕𝚍𝚗'𝚝 𝚜𝚝𝚘𝚛𝚎: <code>{e}</code>", quote=True)
        new_id = copied.id

    st = STATE.get(_key(client, message))
    if st:  # batch collect mode
        st["ids"].append(new_id)
        return await message.reply_text(f"\u2705 𝙰𝚍𝚍𝚎𝚍 ({len(st['ids'])}). 𝚂𝚎𝚗𝚍 𝚖𝚘𝚛𝚎 𝚘𝚛 /done.", quote=True)
    await _send_link(client, message, f"get-{new_id * abs(ch)}")


# ---------- link commands ----------

@Bot.on_message(filters.private & admins & filters.command("genlink"))
async def genlink(client, message):
    if client.is_clone:
        return await message.reply_text(""𝙹𝚞𝚜𝚝 𝚜𝚎𝚗𝚍 𝚊 𝚏𝚒𝚕𝚎 𝚝𝚘 𝚝𝚑𝚒𝚜 𝚋𝚘𝚝 𝚊𝚗𝚍 𝚢𝚘𝚞'𝚕𝚕 𝚐𝚎𝚝 𝚒𝚝𝚜 𝚕𝚒𝚗𝚔.")
    if not _ready(client):
        return await message.reply_text(NOT_READY)
    STATE[_key(client, message)] = {"mode": "lg_single"}
    await message.reply_text(
        "𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝚝𝚑𝚎 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 (𝚠𝚒𝚝𝚑 𝚚𝚞𝚘𝚝𝚎𝚜) 𝚘𝚛 𝚜𝚎𝚗𝚍 𝚒𝚝𝚜 𝚙𝚘𝚜𝚝 𝚕𝚒𝚗𝚔.\n/cancel 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝."
    )


@Bot.on_message(filters.private & admins & filters.command("batch"))
async def batch(client, message):
    if not _ready(client):
        return await message.reply_text(NOT_READY)
    if client.is_clone:
        STATE[_key(client, message)] = {"mode": "lg_collect", "ids": []}
        return await message.reply_text(
            "𝚂𝚎𝚗𝚍 𝚝𝚑𝚎 𝚏𝚒𝚕𝚎𝚜 𝚏𝚘𝚛 𝚝𝚑𝚒𝚜 𝚋𝚊𝚝𝚌𝚑, 𝚝𝚑𝚎𝚗 𝚜𝚎𝚗𝚍 /done.\n/cancel 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝."
        )
    STATE[_key(client, message)] = {"mode": "lg_first"}
    await message.reply_text(
        "𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝚝𝚑𝚎 <b>𝚏𝚒𝚛𝚜𝚝</b> 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 (𝚠𝚒𝚝𝚑 𝚚𝚞𝚘𝚝𝚎𝚜) 𝚘𝚛 𝚜𝚎𝚗𝚍 𝚒𝚝𝚜 𝚕𝚒𝚗𝚔.\n/cancel 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝."
    )


@Bot.on_message(filters.private & admins & filters.command("done"))
async def done(client, message):
    key = _key(client, message)
    st = STATE.get(key)
    if not st or st["mode"] != "lg_collect":
        return await message.reply_text("𝙽𝚘 𝚋𝚊𝚝𝚌𝚑 𝚒𝚗 𝚙𝚛𝚘𝚐𝚛𝚎𝚜𝚜. 𝚂𝚝𝚊𝚛𝚝 𝚘𝚗𝚎 𝚠𝚒𝚝𝚑 /batch.")
    STATE.pop(key, None)
    ids = st["ids"]
    if not ids:
        return await message.reply_text("\u274c 𝚈𝚘𝚞 𝚍𝚒𝚍𝚗'𝚝 𝚜𝚎𝚗𝚍 𝚊𝚗𝚢 𝚏𝚒𝚕𝚎𝚜.")
    abs_ch = abs(client.cfg["db_channel"])
    if len(ids) == 1:
        return await _send_link(client, message, f"get-{ids[0] * abs_ch}")
    await _send_link(client, message, f"get-{min(ids) * abs_ch}-{max(ids) * abs_ch}")


@Bot.on_message(filters.private & filters.command("cancel"))
async def cancel(client, message):
    if STATE.pop(_key(client, message), None) is not None:
        await message.reply_text("𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.")


@Bot.on_message(filters.private & admins & in_state("lg_") & ~filters.regex(r"^/"), group=1)
async def collect(client, message):
    key = _key(client, message)
    st = STATE[key]
    if st["mode"] == "lg_collect":
        if message.media:
            return  # handled by store()
        return await message.reply_text("𝚂𝚎𝚗𝚍 𝚏𝚒𝚕𝚎𝚜 (𝚗𝚘𝚝 𝚝𝚎𝚝), 𝚘𝚛 /done 𝚝𝚘 𝚏𝚒𝚗𝚒𝚜𝚑.", quote=True)

    msg_id = await get_message_id(client, message)
    if not msg_id:
        return await message.reply_text(
            "\u274c 𝚃𝚑𝚊𝚝 𝚒𝚜𝚗'𝚝 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕. 𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝚊𝚐𝚊𝚒𝚗 𝚘𝚛 /cancel.", quote=True
        )
    abs_ch = abs(client.cfg["db_channel"])
    if st["mode"] == "lg_single":
        STATE.pop(key, None)
        await _send_link(client, message, f"get-{msg_id * abs_ch}")
    elif st["mode"] == "lg_first":
        st.update(mode="lg_last", first=msg_id)
        await message.reply_text("𝙽𝚘𝚠 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚝𝚑𝚎 <b>𝚕𝚊𝚜𝚝</b> 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 (𝚘𝚛 𝚜𝚎𝚗𝚍 𝚒𝚝𝚜 𝚕𝚒𝚗𝚔).", quote=True)
    else:
        first = st["first"]
        STATE.pop(key, None)
        await _send_link(client, message, f"get-{first * abs_ch}-{msg_id * abs_ch}")

import asyncio
import secrets
import time
from datetime import datetime
from urllib.parse import quote

import aiohttp
from pyrogram import filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from config import CHANNEL_ID, CLONE_ADMIN_ONLY
from database.database import db
from state import STATE
from helper_func import (
    admins, decode, fill, get_messages, get_readable_time, start_buttons,
    get_unjoined, is_admin, subscribed,
)

MIN_VERIFY_SECONDS = 10  # anti-bypass: verification can't complete faster than this


async def _reply(message, text, markup, pic):
    if pic:
        try:
            return await message.reply_photo(photo=pic, caption=text, reply_markup=markup, quote=True)
        except Exception:
            pass
    return await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True, quote=True)


async def _auto_delete(sent, notice, link, delay):
    await asyncio.sleep(delay)
    for m in sent:
        try:
            await m.delete()
        except Exception:
            pass
    try:
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("\u267b\ufe0f Get Files Again", url=link)]]) if link else None
        await notice.edit_text("<b>\U0001f5d1 Your files were deleted. Tap below to get them again.</b>", reply_markup=markup)
    except Exception:
        pass


async def shorten(cfg, link):
    site = cfg["short_site"].replace("https://", "").replace("http://", "").strip("/")
    api = cfg["short_api"]
    if not site or not api:
        return link
    url = f"https://{site}/api?api={api}&url={quote(link, safe='')}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json(content_type=None)
        return data.get("shortenedUrl") or data.get("shortened_url") or link
    except Exception:
        return link


async def ask_token(client, message, payload):
    uid = message.from_user.id
    token = secrets.token_hex(8)
    await db.create_token(client.bot_id, uid, token, payload)
    link = await shorten(client.cfg, f"https://t.me/{client.username}?start=verify_{token}")
    hours = client.cfg["token_hours"]
    await message.reply_text(
        f"<b>\U0001f512 Access token required\n\nVerify using the button below to unlock files for {hours} hour(s).</b>",
        quote=True,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f510 Verify Now", url=link)]]),
    )


async def handle_verify(client, message, token):
    uid = message.from_user.id
    doc = await db.pop_token(client.bot_id, uid, token)
    if not doc:
        return await message.reply_text("\u274c Invalid or expired token. Open your file link again.", quote=True)
    if time.time() - doc["created"] < MIN_VERIFY_SECONDS:
        return await message.reply_text(
            "\u26a0\ufe0f Verification too fast \u2014 please complete the verification page properly and try again.",
            quote=True,
        )
    hours = client.cfg["token_hours"]
    await db.set_verified(client.bot_id, uid, time.time() + hours * 3600)
    rows = []
    if doc.get("payload"):
        rows.append([InlineKeyboardButton(
            "\U0001f4c2 Get Files", url=f"https://t.me/{client.username}?start={doc['payload']}")])
    await message.reply_text(
        f"<b>\u2705 Verified! Access unlocked for {hours} hour(s).</b>",
        quote=True,
        reply_markup=InlineKeyboardMarkup(rows) if rows else None,
    )


async def deliver(client, message, payload):
    cfg = client.cfg
    user = message.from_user
    if not client.is_clone and (not cfg["db_channel"] or not client.db_channel):
        return await message.reply_text("\u26a0\ufe0f This bot isn't set up yet.", quote=True)
    try:
        argument = (await decode(payload)).split("-")
        abs_ch = abs(cfg["db_channel"])
        if len(argument) == 3 and argument[0] == "get":
            s, e = int(argument[1]) // abs_ch, int(argument[2]) // abs_ch
            ids = list(range(s, e + 1)) if s <= e else list(range(s, e - 1, -1))
        elif len(argument) == 2 and argument[0] == "get":
            ids = [int(argument[1]) // abs_ch]
        else:
            return
    except Exception:
        return await message.reply_text("\u274c Invalid or broken link.", quote=True)

    temp = await message.reply_text("\u23f3 Please wait...", quote=True)
    # Clones deliver with their own file_ids (files are archived in the main DB channel)
    items = await db.get_files(client.bot_id, ids) if client.is_clone else await get_messages(client, ids)
    if not items:
        return await temp.edit_text("\u274c Files not found or deleted.")
    await temp.delete()

    protect = cfg["no_forward"]

    async def send_one(item):
        if client.is_clone:
            return await client.send_cached_media(
                user.id, item["file_id"], caption=item.get("caption") or "", protect_content=protect)
        caption = item.caption.html if item.caption else ""
        return await item.copy(user.id, caption=caption, protect_content=protect, reply_markup=None)

    sent = []
    for item in items:
        try:
            sent.append(await send_one(item))
            await asyncio.sleep(0.4)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                sent.append(await send_one(item))
            except Exception:
                pass
        except Exception:
            pass

    delay = int(cfg["auto_delete"])
    if delay > 0 and sent:
        link = f"https://t.me/{client.username}?start={payload}"
        notice = await message.reply_text(
            f"<b>\u26a0\ufe0f These files will be deleted in {get_readable_time(delay)}. "
            "Forward them somewhere safe now.</b>"
        )
        asyncio.create_task(_auto_delete(sent, notice, link, delay))


@Bot.on_message(filters.command("start") & filters.private & subscribed)
async def start_command(client, message):
    user = message.from_user
    uid = user.id
    cfg = client.cfg
    admin = is_admin(client, uid)
    await db.add_user(client.bot_id, uid)
    payload = message.command[1] if len(message.command) > 1 else None

    # "Create my own clone" deep link from a clone bot
    if payload == "clone" and not client.is_clone:
        if CLONE_ADMIN_ONLY and not admin:
            return await message.reply_text("\u274c Only admins can create clones.", quote=True)
        from plugins.settings import CLONE_HELP
        STATE[(client.bot_id, uid)] = {"mode": "cl_token"}
        return await message.reply_text(CLONE_HELP, quote=True)

    if not cfg["active"] and not admin:
        return await message.reply_text("\U0001f6ab This bot is currently deactivated by its owner.", quote=True)
    if cfg["mode"] == "private" and not admin:
        return await message.reply_text("\U0001f512 This bot is private.", quote=True)

    if not payload:
        return await _reply(message, fill(cfg["start_msg"], user), start_buttons(client), cfg["start_pic"])

    if payload.startswith("verify_"):
        return await handle_verify(client, message, payload[7:])

    if cfg["token_on"] and not admin and not await db.is_verified(client.bot_id, uid):
        return await ask_token(client, message, payload)

    await deliver(client, message, payload)


@Bot.on_message(filters.command("start") & filters.private)
async def not_joined(client, message):
    missing = await get_unjoined(client, message.from_user.id)
    if not missing:
        return await start_command(client, message)

    cfg = client.cfg
    rows, row = [], []
    for i, ch in enumerate(missing, 1):
        row.append(InlineKeyboardButton(f"\U0001f4e2 Join Channel {i}", url=client.invitelinks[ch]))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if len(message.command) > 1:
        rows.append([InlineKeyboardButton(
            "\U0001f504 Try Again", url=f"https://t.me/{client.username}?start={message.command[1]}")])

    await _reply(message, fill(cfg["force_msg"], message.from_user),
                 InlineKeyboardMarkup(rows), cfg["force_pic"])


# ---------------- admin commands (owner / moderators) ----------------

@Bot.on_message(filters.command("users") & filters.private & admins)
async def users_count(client, message):
    await message.reply_text(f"<b>\U0001f465 {await db.count_users(client.bot_id)} users use this bot.</b>")


@Bot.on_message(filters.command("stats") & filters.private & admins)
async def stats(client, message):
    up = get_readable_time((datetime.now() - client.uptime).total_seconds())
    delay = int(client.cfg["auto_delete"])
    await message.reply_text(
        f"<b>\u23f1 Uptime:</b> {up}\n"
        f"<b>\U0001f465 Users:</b> {await db.count_users(client.bot_id)}\n"
        f"<b>\U0001f5d1 Auto delete:</b> {get_readable_time(delay) if delay else 'off'}\n"
        f"<b>\U0001f4e2 Force sub channels:</b> {len(client.force_channels)}"
    )


@Bot.on_message(filters.command("autodelete") & filters.private & admins)
async def autodelete(client, message):
    if len(message.command) < 2:
        cur = int(client.cfg["auto_delete"])
        return await message.reply_text(
            f"Current: <b>{get_readable_time(cur) if cur else 'off'}</b>\n"
            "Usage: <code>/autodelete 600</code> (seconds) or <code>/autodelete off</code>"
        )
    arg = message.command[1].lower()
    if arg in ("off", "0"):
        client.cfg["auto_delete"] = 0
        await client.save_cfg()
        return await message.reply_text("\u2705 Auto delete turned off.")
    if not arg.isdigit():
        return await message.reply_text("\u274c Send a number of seconds or <code>off</code>.")
    client.cfg["auto_delete"] = int(arg)
    await client.save_cfg()
    await message.reply_text(f"\u2705 Auto delete set to {get_readable_time(int(arg))}.")


@Bot.on_message(filters.command("broadcast") & filters.private & admins)
async def broadcast(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast it.")
    users = await db.full_userbase(client.bot_id)
    status = await message.reply_text("\U0001f4e1 Broadcasting...")
    ok = blocked = deleted = failed = 0
    for uid in users:
        try:
            await message.reply_to_message.copy(uid)
            ok += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await message.reply_to_message.copy(uid)
                ok += 1
            except Exception:
                failed += 1
        except UserIsBlocked:
            await db.del_user(client.bot_id, uid)
            blocked += 1
        except InputUserDeactivated:
            await db.del_user(client.bot_id, uid)
            deleted += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"<b>Broadcast done</b>\n\nTotal: {len(users)}\nSuccess: {ok}\n"
        f"Blocked: {blocked}\nDeleted accounts: {deleted}\nFailed: {failed}"
    )

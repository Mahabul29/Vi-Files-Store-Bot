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
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("\u267b\ufe0f 𝙶𝚎𝚝𝚜 𝙵𝚒𝚕𝚎𝚜 𝙰𝚐𝚊𝚒𝚗", url=link)]]) if link else None
        await notice.edit_text("<b>\U0001f5d1 𝚈𝚘𝚞𝚛 𝚏𝚒𝚕𝚎𝚜 𝚠𝚎𝚛𝚎 𝚍𝚎𝚕𝚎𝚝𝚎𝚍. 𝚃𝚊𝚙 𝚋𝚎𝚕𝚘𝚠 𝚝𝚘 𝚐𝚎𝚝 𝚝𝚑𝚎𝚖 𝚊𝚐𝚊𝚒𝚗.</b>", reply_markup=markup)
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
        f"<b>\U0001f512 𝙰𝚌𝚌𝚎𝚜𝚜 𝚝𝚘𝚔𝚎𝚗 𝚛𝚎𝚚𝚞𝚒𝚛𝚎𝚍\n\n𝚅𝚎𝚛𝚒𝚏𝚢 𝚞𝚜𝚒𝚗𝚐 𝚝𝚑𝚎 𝚋𝚞𝚝𝚝𝚘𝚗 𝚋𝚎𝚕𝚘𝚠 𝚝𝚘 𝚞𝚗𝚕𝚘𝚌𝚔 𝚏𝚒𝚕𝚎𝚜 𝚏𝚘𝚛 {hours} 𝚑𝚘𝚞𝚛(𝚜).</b>",
        quote=True,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f510 𝚅𝚎𝚛𝚒𝚏𝚢 𝙽𝚘𝚠", url=link)]]),
    )


async def handle_verify(client, message, token):
    uid = message.from_user.id
    doc = await db.pop_token(client.bot_id, uid, token)
    if not doc:
        return await message.reply_text("\u274c 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚘𝚛 𝚎𝡡𝚙𝚒𝚛𝚎𝚍 𝚝𝚘𝚔𝚎𝚗. 𝙾𝚙𝚎𝚗 𝚢𝚘𝚞𝚛 𝚏𝚒𝚕𝚎 𝚕𝚒𝚗𝚔 𝚊𝚐𝚊𝚒𝚗.", quote=True)
    if time.time() - doc["created"] < MIN_VERIFY_SECONDS:
        return await message.reply_text(
            "\u26a0\ufe0f 𝚅𝚎𝚛𝚒𝚏𝚒𝚌𝚊𝚝𝚒𝚘𝚗 𝚝𝚘𝚘 𝚏𝚊𝚜𝚝 \u2014 𝚙𝚕𝚎𝚊𝚜𝚎 𝚌𝚘𝚖𝚙𝚕𝚎𝚝𝚎 𝚝𝚑𝚎 𝚟𝚎𝚛𝚒𝚏𝚒𝚌𝚊𝚝𝚒𝚘𝚗 𝚙𝚊𝚐𝚎 𝚙𝚛𝚘𝚙𝚎𝚛𝚕𝚢 𝚊𝚗𝚍 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗.",
            quote=True,
        )
    hours = client.cfg["token_hours"]
    await db.set_verified(client.bot_id, uid, time.time() + hours * 3600)
    rows = []
    if doc.get("payload"):
        rows.append([InlineKeyboardButton(
            "\U0001f4c2 𝙶𝚎𝚝 𝙵𝚒𝚕𝚎𝚜", url=f"https://t.me/{client.username}?start={doc['payload']}")])
    await message.reply_text(
        f"<b>\u2705 𝚅𝚎𝚛𝚒𝚏𝚒𝚎𝚍! 𝙰𝚌𝚌𝚎𝚜𝚜 𝚞𝚗𝚕𝚘𝚌𝚔𝚎𝚍 𝚏𝚘𝚛 {hours} 𝚑𝚘𝚞𝚛(𝚜).</b>",
        quote=True,
        reply_markup=InlineKeyboardMarkup(rows) if rows else None,
    )


async def deliver(client, message, payload):
    cfg = client.cfg
    user = message.from_user
    if not client.is_clone and (not cfg["db_channel"] or not client.db_channel):
        return await message.reply_text("\u26a0\ufe0f 𝚃𝚑𝚒𝚜 𝚋𝚘𝚝 𝚒𝚜𝚗'𝚝 𝚜𝚎𝚝 𝚞𝚙 𝚢𝚎𝚝.", quote=True)
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
        return await message.reply_text("\u274c 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚘𝚛 𝚋𝚛𝚘𝚔𝚎𝚗 𝚕𝚒𝚗𝚔.", quote=True)

    temp = await message.reply_text("\u23f3 𝙿𝚕𝚎𝚊𝚜𝚎 𝚠𝚊𝚒𝚝...", quote=True)
    # Clones deliver with their own file_ids (files are archived in the main DB channel)
    items = await db.get_files(client.bot_id, ids) if client.is_clone else await get_messages(client, ids)
    if not items:
        return await temp.edit_text("\u274c 𝙵𝚒𝚕𝚎𝚜 𝚗𝚘𝚝 𝚏𝚘𝚞𝚗𝚍 𝚘𝚛 𝚍𝚎𝚕𝚎𝚝𝚎𝚍.")
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
            f"<b>\u26a0\ufe0f 𝚃𝚑𝚎𝚜𝚎 𝚏𝚒𝚕𝚎𝚜 𝚠𝚒𝚕𝚕 𝚋𝚎 𝚍𝚎𝚕𝚎𝚝𝚎𝚍 𝚒𝚗 {get_readable_time(delay)}. "
            "𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝚝𝚑𝚎𝚖 𝚜𝚘𝚖𝚎𝚠𝚑𝚎𝚛𝚎 𝚜𝚊𝚏𝚎 𝚗𝚘𝚠.</b>"
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
            return await message.reply_text("\u274c 𝙾𝚗𝚕𝚢 𝚊𝚍𝚖𝚒𝚗𝚜 𝚌𝚊𝚗 𝚌𝚛𝚎𝚊𝚝𝚎 𝚌𝚕𝚘𝚗𝚎𝚜.", quote=True)
        from plugins.settings import CLONE_HELP
        STATE[(client.bot_id, uid)] = {"mode": "cl_token"}
        return await message.reply_text(CLONE_HELP, quote=True)

    if not cfg["active"] and not admin:
        return await message.reply_text("\U0001f6ab 𝚃𝚑𝚒𝚜 𝚋𝚘𝚝 𝚒𝚜 𝚌𝚞𝚛𝚛𝚎𝚗𝚝𝚕𝚢 𝚍𝚎𝚊𝚌𝚝𝚒𝚟𝚊𝚝𝚎𝚍 𝚋𝚢 𝚒𝚝𝚜 𝚘𝚠𝚗𝚎𝚛.", quote=True)
    if cfg["mode"] == "private" and not admin:
        return await message.reply_text("\U0001f512 𝚃𝚑𝚒𝚜 𝚋𝚘𝚝 𝚒𝚜 𝚙𝚛𝚒𝚟𝚊𝚝𝚎.", quote=True)

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
        row.append(InlineKeyboardButton(f"\U0001f4e2 𝙹𝚘𝚒𝚗 𝙲𝚑𝚊𝚗𝚗𝚎𝚕 {i}", url=client.invitelinks[ch]))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if len(message.command) > 1:
        rows.append([InlineKeyboardButton(
            "\U0001f504 𝚃𝚛𝚢 𝙰𝚐𝚊𝚒𝚗", url=f"https://t.me/{client.username}?start={message.command[1]}")])

    await _reply(message, fill(cfg["force_msg"], message.from_user),
                 InlineKeyboardMarkup(rows), cfg["force_pic"])


# ---------------- admin commands (owner / moderators) ----------------

@Bot.on_message(filters.command("users") & filters.private & admins)
async def users_count(client, message):
    await message.reply_text(f"<b>\U0001f465 {await db.count_users(client.bot_id)} 𝚞𝚜𝚎𝚛𝚜 𝚞𝚜𝚎 𝚝𝚑𝚒𝚜 𝚋𝚘𝚝.</b>")


@Bot.on_message(filters.command("stats") & filters.private & admins)
async def stats(client, message):
    up = get_readable_time((datetime.now() - client.uptime).total_seconds())
    delay = int(client.cfg["auto_delete"])
    await message.reply_text(
        f"<b>\u23f1 𝚄𝚙𝚝𝚒𝚖𝚎:</b> {up}\n"
        f"<b>\U0001f465 𝚄𝚜𝚎𝚛𝚜:</b> {await db.count_users(client.bot_id)}\n"
        f"<b>\U0001f5d1 𝙰𝚞𝚝𝚘 𝚍𝚎𝚕𝚎𝚝𝚎:</b> {get_readable_time(delay) if delay else '𝚘𝚏𝚏'}\n"
        f"<b>\U0001f4e2 𝙵𝚘𝚛𝚌𝚎 𝚜𝚞𝚋 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜:</b> {len(client.force_channels)}"
    )


@Bot.on_message(filters.command("autodelete") & filters.private & admins)
async def autodelete(client, message):
    if len(message.command) < 2:
        cur = int(client.cfg["auto_delete"])
        return await message.reply_text(
            f"𝙲𝚞𝚛𝚛𝚎𝚗𝚝: <b>{get_readable_time(cur) if cur else '𝚘𝚏𝚏'}</b>\n"
            "𝚄𝚜𝚊𝚐𝚎: <code>/autodelete 600</code> (𝚜𝚎𝚌𝚘𝚗𝚍𝚜) 𝚘𝚛 <code>/autodelete off</code>"
        )
    arg = message.command[1].lower()
    if arg in ("off", "0"):
        client.cfg["auto_delete"] = 0
        await client.save_cfg()
        return await message.reply_text("\u2705 𝙰𝚞𝚝𝚘 𝚍𝚎𝚕𝚎𝚝𝚎 𝚝𝚞𝚛𝚗𝚎𝚍 𝚘𝚏𝚏.")
    if not arg.isdigit():
        return await message.reply_text("\u274c 𝚂𝚎𝚗𝚍 𝚊 𝚗𝚞𝚖𝚋𝚎𝚛 𝚘𝚏 𝚜𝚎𝚌𝚘𝚗𝚍𝚜 𝚘𝚛 <code>off</code>.")
    client.cfg["auto_delete"] = int(arg)
    await client.save_cfg()
    await message.reply_text(f"\u2705 𝙰𝚞𝚝𝚘 𝚍𝚎𝚕𝚎𝚝𝚎 𝚜𝚎𝚝 𝚝𝚘 {get_readable_time(int(arg))}.")


@Bot.on_message(filters.command("broadcast") & filters.private & admins)
async def broadcast(client, message):
    if not message.reply_to_message:
        return await message.reply_text("𝚁𝚎𝚙𝚕𝚢 𝚝𝚘 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚝𝚘 𝚋𝚛𝚘𝚊𝚍𝚌𝚊𝚜𝚝 𝚒𝚝.")
    users = await db.full_userbase(client.bot_id)
    status = await message.reply_text("\U0001f4e1 𝙱𝚛𝚘𝚊𝚍𝚌𝚊𝚜𝚝𝚒𝚗𝚐...")
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
        f"<b>𝙱𝚛𝚘𝚊𝚍𝚌𝚊𝚜𝚝 𝚍𝚘𝚗𝚎</b>\n\n𝚃𝚘𝚝𝚊𝚕: {len(users)}\n𝚂𝚞𝚌𝚌𝚎𝚜𝚜: {ok}\n"
        f"𝙱𝚕𝚘𝚌𝚔𝚎𝚍: {blocked}\n𝙳𝚎𝚕𝚎𝚝𝚎𝚍 𝚊𝚌𝚌𝚘𝚞𝚗𝚝𝚜: {deleted}\n𝙵𝚊𝚒𝚕𝚎𝚍: {failed}"
    )

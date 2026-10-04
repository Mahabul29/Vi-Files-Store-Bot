"""Clone creation (main bot only). Management panel lives in settings.py."""
import re

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from bot import Bot, CLONES, ensure_db_access, start_clone, stop_clone
from config import CLONE_ADMIN_ONLY, OWNER_ID
from database.database import db
from helper_func import admins, is_admin
from plugins.settings import CLONE_HELP, menu_markup, menu_text
from state import STATE, in_state

TOKEN_RE = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,}")


@Bot.on_message(filters.private & in_state("cl_") & ~filters.regex(r"^/"), group=1)
async def clone_token(client, message):
    uid = message.from_user.id
    key = (client.bot_id, uid)
    if CLONE_ADMIN_ONLY and not is_admin(client, uid):
        STATE.pop(key, None)
        return await message.reply_text("\u274c 𝙾𝚗𝚕𝚢 𝚊𝚍𝚖𝚒𝚗𝚜 𝚌𝚊𝚗 𝚌𝚛𝚎𝚊𝚝𝚎 𝚌𝚕𝚘𝚗𝚎𝚜.", quote=True)

    m = TOKEN_RE.search(message.text or "")
    if not m:
        return await message.reply_text("\u274c 𝙽𝚘 𝚋𝚘𝚝 𝚝𝚘𝚔𝚎𝚗 𝚏𝚘𝚞𝚗𝚍. 𝚂𝚎𝚗𝚍 𝚒𝚝 𝚊𝚐𝚊𝚒𝚗 𝚘𝚛 /cancel.", quote=True)
    STATE.pop(key, None)
    token = m.group(0)
    try:
        await message.delete()  # hide the token
    except Exception:
        pass

    wait = await message.reply_text("\u23f3 𝙲𝚛𝚎𝚊𝚝𝚒𝚗𝚐 𝚢𝚘𝚞𝚛 𝚌𝚕𝚘𝚗𝚎...")
    try:
        clone = await start_clone(token, uid)
    except Exception as e:
        return await wait.edit_text(f"\u274c 𝙲𝚕𝚘𝚗𝚎 𝚏𝚊𝚒𝚕𝚎𝚍: <code>{e}</code>")

    await db.add_clone(clone.bot_id, token, uid)
    await clone.save_cfg()

    ok = await ensure_db_access(client, clone)
    if not ok:
        try:
            await client.send_message(
                OWNER_ID,
                f"\u26a0\ufe0f 𝙰𝚍𝚍 @{clone.username} 𝚊𝚜 𝚊𝚍𝚖𝚒𝚗 (𝚙𝚘𝚜𝚝 𝚛𝚒𝚐𝚑𝚝𝚜) 𝚝𝚘 𝚝𝚑𝚎 𝚖𝚊𝚒𝚗 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕.")
        except Exception:
            pass

    await wait.edit_text(
        f"\u2705 <b>𝙲𝚕𝚘𝚗𝚎 𝚌𝚛𝚎𝚊𝚝𝚎𝚍:</b> @{clone.username}\n\n{menu_text(clone)}",
        reply_markup=menu_markup(clone),
    )


@Bot.on_message(filters.command("clones") & filters.private & admins)
async def clones_list(client, message):
    if not CLONES:
        return await message.reply_text("𝙽𝚘 𝚌𝚕𝚘𝚗𝚎𝚜 𝚛𝚞𝚗𝚗𝚒𝚗𝚐.")
    text = "<b>𝚁𝚞𝚗𝚗𝚒𝚗𝚐 𝚌𝚕𝚘𝚗𝚎𝚜:</b>\n\n" + "\n".join(
        f"\u2022 @{c.username} \u2014 <code>{bid}</code> (𝚘𝚠𝚗𝚎𝚛 <code>{c.owner_id}</code>)"
        for bid, c in CLONES.items()
    )
    await message.reply_text(text + "\n\n𝚁𝚎𝚖𝚘𝚟𝚎 𝚠𝚒𝚝𝚑 <code>/delclone BOT_ID</code>")


@Bot.on_message(filters.command("delclone") & filters.private & admins)
async def delclone_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("𝚄𝚜𝚊𝚐𝚎: <code>/delclone BOT_ID</code>")
    bot_id = message.command[1]
    existed = bot_id in CLONES
    await stop_clone(bot_id)
    await db.del_clone(bot_id)
    await db.del_settings(bot_id)
    await db.del_bot_users(bot_id)
    await db.del_bot_files(bot_id)
    await message.reply_text("\u2705 𝙲𝚕𝚘𝚗𝚎 𝚛𝚎𝚖𝚘𝚟𝚎𝚍." if existed else "𝚁𝚎𝚖𝚘𝚟𝚎𝚍 𝚏𝚛𝚘𝚖 𝙳𝙱 (𝚒𝚝 𝚠𝚊𝚜𝚗'𝚝 𝚛𝚞𝚗𝚗𝚒𝚗𝚐).")

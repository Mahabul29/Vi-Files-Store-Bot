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
        return await message.reply_text("❌ Only admins can create clones.", quote=True)

    m = TOKEN_RE.search(message.text or "")
    if not m:
        return await message.reply_text("❌ No bot token found. Send it again or /cancel.", quote=True)
    STATE.pop(key, None)
    token = m.group(0)
    try:
        await message.delete()  # hide the token
    except Exception:
        pass

    wait = await message.reply_text("⏳ Creating your clone...")
    try:
        clone = await start_clone(token, uid)
    except Exception as e:
        return await wait.edit_text(f"❌ Clone failed: <code>{e}</code>")

    await db.add_clone(clone.bot_id, token, uid)
    await clone.save_cfg()

    ok = await ensure_db_access(client, clone)
    if not ok:
        try:
            await client.send_message(
                OWNER_ID,
                f"⚠️ Add @{clone.username} as admin (post rights) to the main DB channel.")
        except Exception:
            pass

    await wait.edit_text(
        f"✅ <b>Clone created:</b> @{clone.username}\n\n{menu_text(clone)}",
        reply_markup=menu_markup(clone),
    )


@Bot.on_message(filters.command("clones") & filters.private & admins)
async def clones_list(client, message):
    if not CLONES:
        return await message.reply_text("No clones running.")
    text = "<b>Running clones:</b>\n\n" + "\n".join(
        f"• @{c.username} — <code>{bid}</code> (owner <code>{c.owner_id}</code>)"
        for bid, c in CLONES.items()
    )
    await message.reply_text(text + "\n\nRemove with <code>/delclone BOT_ID</code>")


@Bot.on_message(filters.command("delclone") & filters.private & admins)
async def delclone_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/delclone BOT_ID</code>")
    bot_id = message.command[1]
    existed = bot_id in CLONES
    await stop_clone(bot_id)
    await db.del_clone(bot_id)
    await db.del_settings(bot_id)
    await db.del_bot_users(bot_id)
    await db.del_bot_files(bot_id)
    await message.reply_text("✅ Clone removed." if existed else "Removed from DB (it wasn't running).")
    

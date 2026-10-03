"""Clone creation + admin management (main bot only)."""
import re

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot, CLONES, start_clone, stop_clone
from config import CLONE_ADMIN_ONLY
from database.database import db
from helper_func import admins, is_admin
from state import STATE, in_state

TOKEN_RE = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,}")


@Bot.on_message(filters.command("clone") & filters.private)
async def clone_cmd(client, message):
    uid = message.from_user.id
    if CLONE_ADMIN_ONLY and not is_admin(client, uid):
        return await message.reply_text("âŒ Only admins can create clones.", quote=True)
    STATE[(client.bot_id, uid)] = {"mode": "cl_token"}
    await message.reply_text(
        "<b>ðŸ¤– Create your own clone</b>\n\n"
        "1. Open @BotFather and create a bot with /newbot\n"
        "2. Copy the bot token\n"
        "3. Send it here (or forward BotFather's message)\n\n"
        "/cancel to abort.",
        quote=True,
    )


@Bot.on_message(filters.private & in_state("cl_") & ~filters.regex(r"^/"), group=1)
async def clone_token(client, message):
    uid = message.from_user.id
    key = (client.bot_id, uid)
    m = TOKEN_RE.search(message.text or "")
    if not m:
        return await message.reply_text("âŒ No bot token found. Send it again or /cancel.", quote=True)
    STATE.pop(key, None)
    token = m.group(0)
    try:
        await message.delete()  # hide the token
    except Exception:
        pass

    wait = await message.reply_text("â³ Creating your clone...")
    try:
        clone = await start_clone(token, uid)
    except Exception as e:
        return await wait.edit_text(f"âŒ Clone failed: <code>{e}</code>")

    await db.add_clone(clone.bot_id, token, uid)
    await clone.save_cfg()
    await wait.edit_text(
        f"âœ… <b>Clone created!</b>\n\nðŸ¤– @{clone.username}\n\n"
        "Open it and send /start to customize. First set the DB channel with <b>TRANSFER DB</b>.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("ðŸš€ Open Clone", url=f"https://t.me/{clone.username}")]]),
    )


@Bot.on_message(filters.command("clones") & filters.private & admins)
async def clones_cmd(client, message):
    if not CLONES:
        return await message.reply_text("No clones running.")
    text = "<b>Running clones:</b>\n\n" + "\n".join(
        f"â€¢ @{c.username} â€” <code>{bid}</code> (owner <code>{c.owner_id}</code>)"
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
    await message.reply_text("âœ… Clone removed." if existed else "Removed from DB (it wasn't running).")

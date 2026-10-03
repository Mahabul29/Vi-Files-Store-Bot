"""Clone creation + admin management (main bot only)."""
import re

from pyrogram import filters
from pyrogram.types import ChatPrivileges, InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot, CLONES, start_clone, stop_clone
from config import CLONE_ADMIN_ONLY
from config import CHANNEL_ID, LOGGER, OWNER_ID
from database.database import db
from helper_func import admins, is_admin
from state import STATE, in_state

TOKEN_RE = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,}")


@Bot.on_message(filters.command("clone") & filters.private)
async def clone_cmd(client, message):
    uid = message.from_user.id
    if CLONE_ADMIN_ONLY and not is_admin(client, uid):
        return await message.reply_text("❌ Only admins can create clones.", quote=True)
    STATE[(client.bot_id, uid)] = {"mode": "cl_token"}
    await message.reply_text(
        "<b>🤖 Create your own clone</b>\n\n"
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

    # Give the clone access to the main DB channel
    ok = clone.db_channel is not None
    if not ok:
        try:
            await client.promote_chat_member(
                CHANNEL_ID, int(clone.bot_id),
                privileges=ChatPrivileges(
                    can_post_messages=True, can_edit_messages=True, can_delete_messages=True),
            )
        except Exception as e:
            LOGGER.warning(f"Auto-promote of @{clone.username} failed: {e}")
        ok = await clone.setup_db_channel()
    note = ""
    if not ok:
        note = (f"\n\n⚠️ The clone can't access the main DB channel yet. "
                f"The main owner must add @{clone.username} as admin there.")
        try:
            await client.send_message(
                OWNER_ID, f"⚠️ Add @{clone.username} as admin (post rights) to the main DB channel.")
        except Exception:
            pass
    await wait.edit_text(
        f"✅ <b>Clone created!</b>\n\n🤖 @{clone.username}\n\n"
        "Open it, send /start to customize, then send files to it to get links "
        "(they are stored in the main DB channel)." + note,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🚀 Open Clone", url=f"https://t.me/{clone.username}")]]),
    )


@Bot.on_message(filters.command("clones") & filters.private & admins)
async def clones_cmd(client, message):
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
    

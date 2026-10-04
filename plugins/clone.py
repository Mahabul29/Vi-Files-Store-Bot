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


def to_typewriter(text: str) -> str:
    """
    Converts standard ASCII alphanumeric characters to Unicode Mathematical Typewriter font.
    Example: 'hello 123' -> '𝚑𝚎𝚕𝚕𝚘 𝟷𝟸𝟹'
    """
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    typewriter = "𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿 call𝚠𝚇𝚈𝚉𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"
    trans_table = str.maketrans(normal, typewriter)
    return text.translate(trans_table)


@Bot.on_message(filters.private & in_state("cl_") & ~filters.regex(r"^/"), group=1)
async def clone_token(client, message):
    uid = message.from_user.id
    key = (client.bot_id, uid)
    if CLONE_ADMIN_ONLY and not is_admin(client, uid):
        STATE.pop(key, None)
        return await message.reply_text(f"❌ {to_typewriter('Only admins can create clones.')}", quote=True)

    m = TOKEN_RE.search(message.text or "")
    if not m:
        return await message.reply_text(f"❌ {to_typewriter('No bot token found. Send it again or /cancel.')}", quote=True)
    STATE.pop(key, None)
    token = m.group(0)
    try:
        await message.delete()  # hide the token
    except Exception:
        pass

    wait = await message.reply_text(f"⏳ {to_typewriter('Creating your clone...')}")
    try:
        clone = await start_clone(token, uid)
    except Exception as e:
        return await wait.edit_text(f"❌ {to_typewriter('Clone failed:')} <code>{e}</code>")

    await db.add_clone(clone.bot_id, token, uid)
    await clone.save_cfg()

    ok = await ensure_db_access(client, clone)
    if not ok:
        try:
            await client.send_message(
                OWNER_ID,
                f"⚠️ {to_typewriter('Add')} @{clone.username} {to_typewriter('as admin (post rights) to the main DB channel.')}")
        except Exception:
            pass

    success_text = (
        f"✅ <b>{to_typewriter('Clone created:')}</b> @{clone.username}\n\n"
        f"{to_typewriter(menu_text(clone))}"
    )

    await wait.edit_text(
        success_text,
        reply_markup=menu_markup(clone),
    )


@Bot.on_message(filters.command("clones") & filters.private & admins)
async def clones_list(client, message):
    if not CLONES:
        return await message.reply_text(to_typewriter("No clones running."))
        
    clone_items = [
        f"• @{c.username} — <code>{bid}</code> ({to_typewriter('owner')} <code>{c.owner_id}</code>)"
        for bid, c in CLONES.items()
    ]
    
    text = (
        f"<b>{to_typewriter('Running clones:')}</b>\n\n" +
        "\n".join(clone_items) +
        f"\n\n{to_typewriter('Remove with')} <code>/delclone BOT_ID</code>"
    )
    await message.reply_text(text)


@Bot.on_message(filters.command("delclone") & filters.private & admins)
async def delclone_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text(f"{to_typewriter('Usage:')} <code>/delclone BOT_ID</code>")
    bot_id = message.command[1]
    existed = bot_id in CLONES
    await stop_clone(bot_id)
    await db.del_clone(bot_id)
    await db.del_settings(bot_id)
    await db.del_bot_users(bot_id)
    await db.del_bot_files(bot_id)
    
    msg = f"✅ {to_typewriter('Clone removed.')}" if existed else to_typewriter("Removed from DB (it was not running).")
    await message.reply_text(msg)

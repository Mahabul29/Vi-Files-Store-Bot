from pyrogram import filters

from bot import Bot, CLONES, start_clone
from config import ADMINS
from database.database import db


@Bot.on_message(filters.command("clone") & filters.private & filters.user(ADMINS))
async def clone_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: <code>/clone BOT_TOKEN</code>\n\n"
            "Create the bot at @BotFather, then add it as <b>admin</b> to the DB channel "
            "and every force sub channel before cloning."
        )
    token = message.command[1].strip()
    try:
        await message.delete()  # hide the token
    except Exception:
        pass
    wait = await message.reply_text("â³ Starting clone...")
    try:
        clone = await start_clone(token)
    except Exception as e:
        return await wait.edit_text(f"âŒ Clone failed: <code>{e}</code>")
    await db.add_clone(token.split(":")[0], token, message.from_user.id)
    await wait.edit_text(f"âœ… Clone started: @{clone.username}")


@Bot.on_message(filters.command("clones") & filters.private & filters.user(ADMINS))
async def clones_cmd(client, message):
    if not CLONES:
        return await message.reply_text("No clones running.")
    text = "<b>Running clones:</b>\n\n" + "\n".join(
        f"â€¢ @{c.username} â€” <code>{bid}</code>" for bid, c in CLONES.items()
    )
    await message.reply_text(text + "\n\nRemove with <code>/delclone BOT_ID</code>")


@Bot.on_message(filters.command("delclone") & filters.private & filters.user(ADMINS))
async def delclone_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/delclone BOT_ID</code>")
    bot_id = message.command[1]
    c = CLONES.pop(bot_id, None)
    if c:
        try:
            await c.stop()
        except Exception:
            pass
    await db.del_clone(bot_id)
    await message.reply_text("âœ… Clone removed." if c else "Removed from DB (it wasn't running).")

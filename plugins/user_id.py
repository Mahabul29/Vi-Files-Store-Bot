from pyrogram import filters
from bot import Bot


@Bot.on_message(filters.command("id") & filters.private)
async def show_id(client, message):
    await message.reply_text(f"<b>Your ID:</b> <code>{message.from_user.id}</code>", quote=True)


@Bot.on_message(filters.command("ping") & filters.private)
async def ping(client, message):
    await message.reply_text("ðŸ“ Pong!", quote=True)

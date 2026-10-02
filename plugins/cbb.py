from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from config import START_MESSAGE
from plugins.start import START_BUTTONS, fill


async def _edit(query, text, markup):
    if query.message.photo:
        await query.message.edit_caption(text, reply_markup=markup)
    else:
        await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)


@Bot.on_callback_query()
async def cb_handler(client, query):
    data = query.data
    if data == "about":
        await _edit(
            query,
            f"<b>â—‹ Bot: @{client.username}\nâ—‹ Language: Python 3\n"
            "â—‹ Library: Pyrogram\nâ—‹ Database: MongoDB</b>",
            InlineKeyboardMarkup([[
                InlineKeyboardButton("â¬…ï¸ Back", callback_data="start"),
                InlineKeyboardButton("ðŸ”’ Close", callback_data="close"),
            ]]),
        )
    elif data == "start":
        await _edit(query, fill(START_MESSAGE, query.from_user), START_BUTTONS)
    elif data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except Exception:
            pass
    await query.answer()

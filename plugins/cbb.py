from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from config import CLONE_ADMIN_ONLY
from helper_func import fill, is_admin, start_buttons
from plugins.settings import CLONE_HELP
from state import STATE

HELP_TEXT = (
    "<b>\U0001f4d6 Help</b>\n\n"
    "\u2022 Open a shared link to get the stored files.\n"
    "\u2022 If asked, join the required channel(s), then tap <b>Try Again</b>.\n"
    "\u2022 Files may be auto deleted after some time \u2014 forward them to your saved messages.\n\n"
    "<b>Want your own bot?</b> Tap <b>CREATE MY OWN CLONE</b>."
)


def _nav():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("BACK", callback_data="start"),
        InlineKeyboardButton("CLOSE", callback_data="close"),
    ]])


async def _edit(query, text, markup):
    if query.message.photo:
        await query.message.edit_caption(text, reply_markup=markup)
    else:
        await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)


@Bot.on_callback_query(filters.regex(r"^(help|about|clone|start|close)$"))
async def cb_handler(client, query):
    data = query.data
    if data == "help":
        await _edit(query, HELP_TEXT, _nav())

    elif data == "about":
        await _edit(
            query,
            f"<b>\u25cb Bot: @{client.username}\n\u25cb Language: Python 3\n"
            "\u25cb Library: Pyrogram\n\u25cb Database: MongoDB</b>",
            _nav(),
        )

    elif data == "clone":  # main bot only (clones use a URL button)
        if CLONE_ADMIN_ONLY and not is_admin(client, query.from_user.id):
            return await query.answer("Only admins can create clones.", show_alert=True)
        STATE[(client.bot_id, query.from_user.id)] = {"mode": "cl_token"}
        await _edit(query, CLONE_HELP, InlineKeyboardMarkup(
            [[InlineKeyboardButton("BACK", callback_data="start")]]))

    elif data == "start":
        STATE.pop((client.bot_id, query.from_user.id), None)
        await _edit(query, fill(client.cfg["start_msg"], query.from_user), start_buttons(client))

    elif data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except Exception:
            pass
    await query.answer()

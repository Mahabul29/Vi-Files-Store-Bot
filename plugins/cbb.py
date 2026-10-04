from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from config import CLONE_ADMIN_ONLY
from helper_func import fill, is_admin, start_buttons
from plugins.settings import CLONE_HELP
from state import STATE

HELP_TEXT = (
    "<b>\U0001f4d6 𝙷𝚎𝚕𝚙</b>\n\n"
    "\u2022 𝙾𝚙𝚎𝚗 𝚊 𝚜𝚑𝚊𝚛𝚎𝚍 𝚕𝚒𝚗𝚔 𝚝𝚘 𝚐𝚎𝚝 𝚝𝚑𝚎 𝚜𝚝𝚘𝚛𝚎𝚍 𝚏𝚒𝚕𝚎𝚜.\n"
    "\u2022 𝙸𝚏 𝚊𝚜𝚔𝚎𝚍, 𝚓𝚘𝚒𝚗 𝚝𝚑𝚎 𝚛𝚎𝚚𝚞𝚒𝚛𝚎𝚍 𝚌𝚑𝚊𝚗𝚗𝚎𝚕(𝚜), 𝚝𝚑𝚎𝚗 𝚝𝚊𝚙 <b>𝚃𝚛𝚢 𝙰𝚐𝚊𝚒𝚗</b>.\n"
    "\u2022 𝙵𝚒𝚕𝚎𝚜 𝚖𝚊𝚢 𝚋𝚎 𝚊𝚞𝚝𝚘 𝚍𝚎𝚕𝚎𝚝𝚎𝚍 𝚊𝚏𝚝𝚎𝚛 𝚜𝚘𝚖𝚎 𝚝𝚒𝚖𝚎 \u2014 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚝𝚑𝚎𝚖 𝚝𝚘 𝚢𝚘𝚞𝚛 𝚜𝚊𝚟𝚎𝚍 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜.\n\n"
    "<b>𝚆𝚊𝚗𝚝 𝚢𝚘𝚞𝚛 𝚘𝚠𝚗 𝚋𝚘𝚝?</b> 𝚃𝚊𝚙 <b>𝙲𝚁𝙴𝙰𝚃𝙴 𝙼𝚈 𝙾𝚆𝙽 𝙲𝙻𝙾𝙽𝙴</b>."
)


def _nav():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("𝙱𝙰𝙲𝙺", callback_data="start"),
        InlineKeyboardButton("𝙲𝙻𝙾𝚂𝙴", callback_data="close"),
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
            f"<b>\u25cb 𝙱𝚘𝚝: @{client.username}\n\u25cb 𝙻𝚊𝚗𝚐𝚞𝚊𝚐𝚎: Python 3\n"
            "\u25cb 𝙻𝚒𝚋𝚛𝚊𝚛𝚢: Pyrogram\n\u25cb 𝙳𝚊𝚝𝚊𝚋𝚊𝚜𝚎: MongoDB</b>",
            _nav(),
        )

    elif data == "clone":  # main bot only (clones use a URL button)
        if CLONE_ADMIN_ONLY and not is_admin(client, query.from_user.id):
            return await query.answer("𝙾𝚗𝚕𝚢 𝚊𝚍𝚖𝚒𝚗𝚜 𝚌𝚊𝚗 𝚌𝚛𝚎𝚊𝚝𝚎 𝚌𝚕𝚘𝚗𝚎𝚜.", show_alert=True)
        STATE[(client.bot_id, query.from_user.id)] = {"mode": "cl_token"}
        await _edit(query, CLONE_HELP, InlineKeyboardMarkup(
            [[InlineKeyboardButton("𝙱𝙰𝙲𝙺", callback_data="start")]]))

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

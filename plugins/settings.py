"""Clone management panel — controlled entirely from the MAIN bot."""
import html
import re
from datetime import datetime

from pyrogram import filters
from pyrogram.types import ChatPrivileges, InlineKeyboardButton as B, InlineKeyboardMarkup as M

from bot import Bot, CLONES, restart_clone, stop_clone
from config import CLONE_ADMIN_ONLY, START_MESSAGE
from database.database import db
from helper_func import forward_info, get_readable_time, is_admin
from state import STATE, in_state

CLONE_HELP = (
    "<b>\U0001f916 𝙲𝚛𝚎𝚊𝚝𝚎 𝚢𝚘𝚞𝚛 𝚘𝚠𝚗 𝚌𝚕𝚘𝚗𝚎</b>\n\n"
    "1. 𝙾𝚙𝚎𝚗 @BotFather 𝚊𝚗𝚍 𝚌𝚛𝚎𝚊𝚝𝚎 𝚊 𝚋𝚘𝚝 𝚠𝚒𝚝𝚑 /newbot\n"
    "2. 𝙲𝚘𝚙𝚢 𝚝𝚑𝚎 𝚋𝚘𝚝 𝚝𝚘𝚔𝚎𝚗\n"
    "3. 𝚂𝚎𝚗𝚍 𝚒𝚝 𝚑𝚎𝚛𝚎 (𝚘𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 BotFather'𝚜 𝚖𝚎𝚜𝚜𝚊𝚐𝚎)\n\n"
    "/cancel 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝."
)


def cd(t, act, arg=None):
    return f"cs:{t.bot_id}:{act}" + (f":{arg}" if arg is not None else "")


def can_manage(client, t, uid):
    return uid == t.owner_id or is_admin(client, uid)


# ---------------- clone list ----------------

def clones_view(client, uid):
    mine = [c for c in CLONES.values() if can_manage(client, c, uid)]
    rows = [[B(f"\U0001f916 @{c.username}", callback_data=f"mc:sel:{c.bot_id}")] for c in mine]
    rows.append([B("\u2795 𝙰𝚍𝚍 𝙲𝚕𝚘𝚗𝚎", callback_data="mc:add")])
    text = "\U0001f916 <b>𝚈𝚘𝚞𝚛 𝙲𝚕𝚘𝚗𝚎𝚜</b>\n\n" + (
        "𝚂𝚎𝚕𝚎𝚌𝚝 𝚊 𝚌𝚕𝚘𝚗𝚎 𝚝𝚘 𝚌𝚞𝚜𝚝𝚘𝚖𝚒𝚣𝚎 𝚒𝚝." if mine else "𝚈𝚘𝚞 𝚍𝚘𝚗'𝚝 𝚑𝚊𝚟𝚎 𝚊𝚗𝚢 𝚌𝚕𝚘𝚗𝚎𝚜 𝚢𝚎𝚝."
    )
    return text, M(rows)


# ---------------- panel ----------------

def _onoff(v):
    return "𝙾𝙽 \u2705" if v else "𝙾𝙵𝙵 \u274c"


def menu_text(t):
    text = (
        "\U0001fa84 <u><b>𝙲𝚞𝚜𝚝𝚘𝚖𝚒𝚣𝚎 𝙲𝚕𝚘𝚗𝚎</b></u>\n\n"
        f"\u279b <b>𝙽𝚊𝚖𝚎:</b> {html.escape(t.display_name or '')}\n\n"
        "<i>𝙲𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎 𝚈𝚘𝚞𝚛 𝙲𝚕𝚘𝚗𝚎 𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝚄𝚜𝚒𝚗𝚐 𝙶𝚒𝚟𝚎𝚗 𝙱𝚞𝚝𝚝𝚘𝚗𝚜</i>"
    )
    return text


def menu_markup(t):
    return M([
        [B("𝚂𝚃𝙰𝚁𝚃 𝙼𝚂𝙶", callback_data=cd(t, "start")), B("𝙵𝙾𝚁𝙲𝙴 𝚂𝚄𝙱", callback_data=cd(t, "force"))],
        [B("𝙼𝙾𝙳𝙴𝚁𝙰𝚃𝙾𝚁𝚂", callback_data=cd(t, "mods")), B("𝙰𝚄𝚃𝙾 𝙳𝙴𝙻𝙴𝚃𝙴", callback_data=cd(t, "ad"))],
        [B("𝙽𝙾 𝙵𝙾𝚁𝚆𝙰𝚁𝙳", callback_data=cd(t, "nf")), B("𝙰𝙲𝙲𝙴𝚂𝚂 𝚃𝙾𝙺𝙴𝙽", callback_data=cd(t, "tok"))],
        [B("𝙳𝙴𝙰𝙲𝚃𝙸𝚅𝙰𝚃𝙴" if t.cfg["active"] else "𝙰𝙲𝚃𝙸𝚅𝙰𝚃𝙴", callback_data=cd(t, "deact")),
         B("𝙼𝙾𝙳𝙴", callback_data=cd(t, "mode"))],
        [B("𝚁𝙴𝚂𝚃𝙰𝚁𝚃", callback_data=cd(t, "restart")), B("𝚂𝚃𝙰𝚃𝚂", callback_data=cd(t, "stats"))],
        [B("𝙳𝙴𝙻𝙴𝚃𝙴", callback_data=cd(t, "del"))],
        [B("𝙱𝙰𝙲𝙺", callback_data="mc:menu")],
    ])


async def render(t, name):
    cfg = t.cfg
    back = [B("\u2b05\ufe0f 𝙱𝚊𝚌𝚔", callback_data=cd(t, "menu"))]

    if name == "start":
        pic = "𝚜𝚎𝚝 \u2705" if cfg["start_pic"] else "𝚗𝚘𝚝 𝚜𝚎𝚝"
        return (
            f"\U0001f4dd <b>𝚂𝚝𝚊𝚛𝚝 𝙼𝚎𝚜𝚜𝚊𝚐𝚎</b>\n\n{cfg['start_msg']}\n\n\U0001f5bc 𝙿𝚒𝚌𝚝𝚞𝚛𝚎: {pic}",
            M([[B("\u270f\ufe0f 𝚂𝚎𝚝 𝙼𝚎𝚜𝚜𝚊𝚐𝚎", callback_data=cd(t, "startmsg")),
                B("\U0001f5bc 𝚂𝚎𝚝 𝙿𝚒𝚌𝚝𝚞𝚛𝚎", callback_data=cd(t, "startpic"))],
               [B("\u267b\ufe0f 𝚁𝚎𝚜𝚎𝚝", callback_data=cd(t, "startreset"))], back]),
        )

    if name == "force":
        rows = [[B(f"\u274c {t.fsub_titles.get(ch, ch)}", callback_data=cd(t, "fdel", ch))]
                for ch in cfg["force"]]
        if len(cfg["force"]) < 4:
            rows.append([B("\u2795 𝙰𝚍𝚍 𝙲𝚑𝚊𝚗𝚗𝚎𝚕", callback_data=cd(t, "fadd"))])
        rows.append(back)
        return (
            f"\U0001f4e2 <b>𝙵𝚘𝚛𝚌𝚎 𝚂𝚞𝚋</b> ({len(cfg['force'])}/4)\n\n"
            "𝚄𝚜𝚎𝚛𝚜 𝚖𝚞𝚜𝚝 𝚓𝚘𝚒𝚗 𝚝𝚑𝚎𝚜𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜 𝚋𝚎𝚏𝚘𝚛𝚎 𝚐𝚎𝚝𝚝𝚒𝚗𝚐 𝚏𝚒𝚕𝚎𝚜.\n𝚃𝚊𝚙 𝚊 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚝𝚘 𝚛𝚎𝚖𝚘𝚟𝚎 𝚒𝚝.",
            M(rows),
        )

    if name == "mods":
        rows = [[B(f"\u274c {m}", callback_data=cd(t, "mdel", m))] for m in cfg["mods"]]
        rows.append([B("\u2795 𝙰𝚍𝚍 𝙼𝚘𝚍𝚎𝚛𝚊𝚝𝚘𝚛", callback_data=cd(t, "madd"))])
        rows.append(back)
        return (
            "\U0001f46e <b>𝙼𝚘𝚍𝚎𝚛𝚊𝚝𝚘𝚛𝚜</b>\n\n𝙼𝚘𝚍𝚎𝚛𝚊𝚝𝚘𝚛𝚜 𝚌𝚊𝚗 𝚜𝚝𝚘𝚛𝚎 𝚏𝚒𝚕𝚎𝚜 𝚒𝚗 𝚝𝚑𝚎 𝚌𝚕𝚘𝚗𝚎 𝚊𝚗𝚍 𝚞𝚜𝚎 𝚒𝚝𝚜 𝚊𝚍𝚖𝚒𝚗 𝚌𝚘𝚖𝚖𝚊𝚗𝚍𝚜.\n"
            "𝚃𝚊𝚙 𝚊𝚗 𝙸𝙳 𝚝𝚘 𝚛𝚎𝚖𝚘𝚟𝚎 𝚒𝚝.",
            M(rows),
        )

    if name == "ad":
        cur = int(cfg["auto_delete"])
        return (
            f"\U0001f5d1 <b>𝙰𝚞𝚝𝚘 𝙳𝚎𝚕𝚎𝚝𝚎</b>\n\n𝙲𝚞𝚛𝚛𝚎𝚗𝚝: <b>{get_readable_time(cur) if cur else '𝙾𝙵𝙵'}</b>\n\n"
            "𝙳𝚎𝚕𝚒𝚟𝚎𝚛𝚎𝚍 𝚏𝚒𝚕𝚎𝚜 𝚊𝚛𝚎 𝚍𝚎𝚕𝚎𝚝𝚎𝚍 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚞𝚜𝚎𝚛'𝚜 𝚌𝚑𝚊𝚝 𝚊𝚏𝚝𝚎𝚛 𝚝𝚑𝚒𝚜 𝚝𝚒𝚖𝚎.",
            M([[B("𝙾𝙵𝙵", callback_data=cd(t, "adset", 0)), B("5 𝚖𝚒𝚗", callback_data=cd(t, "adset", 300)),
                B("10 𝚖𝚒𝚗", callback_data=cd(t, "adset", 600))],
               [B("30 𝚖𝚒𝚗", callback_data=cd(t, "adset", 1800)), B("1 𝚑𝚘𝚞𝚛", callback_data=cd(t, "adset", 3600)),
                B("\u270f\ufe0f 𝙲𝚞𝚜𝚝𝚘𝚖", callback_data=cd(t, "adcustom"))], back]),
        )

    if name == "nf":
        on = cfg["no_forward"]
        return (
            f"\U0001f6ab <b>𝙽𝚘 𝙵𝚘𝚛𝚠𝚊𝚛𝚍</b>\n\n𝚂𝚝𝚊𝚝𝚞𝚜: <b>{_onoff(on)}</b>\n\n𝚆𝚑𝚎𝚗 𝙾𝙽, 𝚏𝚒𝚕𝚎𝚜 𝚌𝚊𝚗'𝚝 𝚋𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚍 𝚘𝚛 𝚜𝚊𝚟𝚎𝚍.",
            M([[B("𝚃𝚞𝚛𝚗 𝙾𝙵𝙵" if on else "𝚃𝚞𝚛𝚗 𝙾𝙽", callback_data=cd(t, "nftoggle"))], back]),
        )

    if name == "tok":
        api = cfg["short_api"]
        masked = ("\u2022\u2022\u2022" + api[-4:]) if api else "𝚗𝚘𝚝 𝚜𝚎𝚝"
        on = cfg["token_on"]
        return (
            "\U0001f511 <b>𝙰𝚌𝚌𝚎𝚜𝚜 𝚃𝚘𝚔𝚎𝚗</b>\n\n"
            f"𝚂𝚝𝚊𝚝𝚞𝚜: <b>{_onoff(on)}</b>\n"
            f"𝚂𝚑𝚘𝚛𝚝𝚎𝚗𝚎𝚛: <code>{html.escape(cfg['short_site'] or '𝚗𝚘𝚝 𝚜𝚎𝚝')}</code>\n"
            f"𝙰𝙿𝙸: <code>{masked}</code>\n"
            f"𝚅𝚊𝚕𝚒𝚍𝚒𝚝𝚢: <b>{cfg['token_hours']}𝚑</b>\n\n"
            "𝚄𝚜𝚎𝚛𝚜 𝚟𝚎𝚛𝚒𝚏𝚢 𝚝𝚑𝚛𝚘𝚞𝚐𝚑 𝚢𝚘𝚞𝚛 𝚜𝚑𝚘𝚛𝚝𝚎𝚗𝚎𝚛 𝚕𝚒𝚗𝚔 𝚝𝚘 𝚞𝚗𝚕𝚘𝚌𝚔 𝚏𝚒𝚕𝚎𝚜 𝚏𝚘𝚛 𝚝𝚑𝚎 𝚟𝚊𝚕𝚒𝚍𝚒𝚝𝚢 𝚙𝚎𝚛𝚒𝚘𝚍.",
            M([[B("𝚃𝚞𝚛𝚗 𝙾𝙵𝙵" if on else "𝚃𝚞𝚛𝚗 𝙾𝙽", callback_data=cd(t, "toktoggle"))],
               [B("\U0001f310 𝚂𝚎𝚝 𝚂𝚒𝚝𝚎", callback_data=cd(t, "toksite")), B("\U0001f511 𝚂𝚎𝚝 𝙰𝙿𝙸", callback_data=cd(t, "tokapi"))],
               [B("6𝚑", callback_data=cd(t, "tokh", 6)), B("12𝚑", callback_data=cd(t, "tokh", 12)),
                B("24𝚑", callback_data=cd(t, "tokh", 24)), B("48𝚑", callback_data=cd(t, "tokh", 48))], back]),
        )

    if name == "mode":
        m = cfg["mode"]
        return (
            f"\U0001f501 <b>𝙼𝚘𝚍𝚎</b>\n\n𝙲𝚞𝚛𝚛𝚎𝚗𝚝: <b>{m.upper()}</b>\n\n"
            "\u2022 𝙿𝚄𝙱𝙻𝙸𝙲 \u2013 𝚊𝚗𝚢𝚘𝚗𝚎 𝚠𝚒𝚝𝚑 𝚊 𝚕𝚒𝚗𝚔 𝚌𝚊𝚗 𝚐𝚎𝚝 𝚏𝚒𝚕𝚎𝚜\n"
            "\u2022 𝙿𝚁𝙸𝚅𝙰𝚃𝙴 \u2013 𝚘𝚗𝚕𝚢 𝚝𝚑𝚎 𝚘𝚠𝚗𝚎𝚛 𝚊𝚗𝚍 𝚖𝚘𝚍𝚎𝚛𝚊𝚝𝚘𝚛𝚜 𝚌𝚊𝚗 𝚐𝚎𝚝 𝚏𝚒𝚕𝚎𝚜",
            M([[B("𝚂𝚠𝚒𝚝𝚌𝚑 𝚝𝚘 𝙿𝚁𝙸𝚅𝙰𝚃𝙴" if m == "public" else "𝚂𝚠𝚒𝚝𝚌𝚑 𝚝𝚘 𝙿𝚄𝙱𝙻𝙸𝙲",
                  callback_data=cd(t, "modetoggle"))], back]),
        )

    if name == "stats":
        users = await db.count_users(t.bot_id)
        up = get_readable_time((datetime.now() - t.uptime).total_seconds())
        ad = int(cfg["auto_delete"])
        return (
            "\U0001f4ca <b>𝚂𝚝𝚊𝚝𝚜</b>\n\n"
            f"\U0001f916 𝙱𝚘𝚝: @{t.username}\n"
            f"\U0001f465 𝚄𝚜𝚎𝚛𝚜: <b>{users}</b>\n"
            f"\u23f1 𝚄𝚙𝚝𝚒𝚖𝚎: <b>{up}</b>\n"
            f"\u26a1 𝚂𝚝𝚊𝚝𝚞𝚜: <b>{'𝙰𝚌𝚝𝚒𝚟𝚎' if cfg['active'] else '𝙳𝚎𝚊𝚌𝚝𝚒𝚟𝚊𝚝𝚎𝚍'}</b>\n"
            "\U0001f5c4 𝚂𝚝𝚘𝚛𝚊𝚐𝚎: <b>𝙼𝚊𝚒𝚗 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕</b>\n"
            f"\U0001f501 𝙼𝚘𝚍𝚎: <b>{cfg['mode'].upper()}</b>\n"
            f"\U0001f4e2 𝙵𝚘𝚛𝚌𝚎 𝚜𝚞𝚋: <b>{len(t.force_channels)}</b>\n"
            f"\U0001f46e 𝙼𝚘𝚍𝚎𝚛𝚊𝚝𝚘𝚛𝚜: <b>{len(cfg['mods'])}</b>\n"
            f"\U0001f5d1 𝙰𝚞𝚝𝚘 𝚍𝚎𝚕𝚎𝚝𝚎: <b>{get_readable_time(ad) if ad else '𝙾𝙵𝙵'}</b>\n"
            f"\U0001f6ab 𝙽𝚘 𝚏𝚘𝚛𝚠𝚊𝚛𝚍: <b>{_onoff(cfg['no_forward'])}</b>\n"
            f"\U0001f511 𝙰𝚌𝚌𝚎𝚜𝚜 𝚝𝚘𝚔𝚎𝚗: <b>{_onoff(cfg['token_on'])}</b>",
            M([back]),
        )

    if name == "del":
        return (
            "\u26a0\ufe0f <b>𝙳𝚎𝚕𝚎𝚝𝚎 𝚝𝚑𝚒𝚜 𝚌𝚕𝚘𝚗𝚎?</b>\n\n𝚃𝚑𝚒𝚜 𝚛𝚎𝚖𝚘𝚟𝚎𝚜 𝚝𝚑𝚎 𝚌𝚕𝚘𝚗𝚎 𝚊𝚗𝚍 𝚊𝚕𝚕 𝚒𝚝𝚜 𝚍𝚊𝚝𝚊 𝚙𝚎𝚛𝚖𝚊𝚗𝚎𝚗𝚝𝚕𝚢.",
            M([[B("\u2705 𝚈𝚎𝚜, 𝚍𝚎𝚕𝚎𝚝𝚎", callback_data=cd(t, "delyes")), B("\u274c 𝙽𝚘", callback_data=cd(t, "menu"))]]),
        )

    return menu_text(t), menu_markup(t)


async def _show(q, text, markup):
    try:
        await q.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass


# ---------------- commands ----------------

@Bot.on_message(filters.private & (filters.command("clone") | filters.command("settings")))
async def clones_cmd(client, message):
    text, markup = clones_view(client, message.from_user.id)
    await message.reply_text(text, reply_markup=markup, quote=True)


# ---------------- callbacks ----------------

PROMPTS = {
    "startmsg": ("cs_startmsg",
                 "𝚂𝚎𝚗𝚍 𝚝𝚑𝚎 𝚗𝚎𝚠 <b>𝚜𝚝𝚊𝚛𝚝 𝚖𝚎𝚜𝚜𝚊𝚐𝚎</b> (HTML allowed).\n"
                 "𝙵𝚒𝚕𝚕𝚒𝚗𝚐𝚜: <code>{first} {last} {username} {mention} {id}</code>", "start"),
    "startpic": ("cs_startpic", "𝚂𝚎𝚗𝚍 𝚊 𝚍𝚒𝚛𝚎𝚌𝚝 <b>𝚒𝚖𝚊𝚐𝚎 𝚄𝚁𝙻</b> (https://\u2026) 𝚝𝚘 𝚞𝚜𝚎 𝚊𝚜 𝚝𝚑𝚎 𝚜𝚝𝚊𝚛𝚝 𝚙𝚒𝚌𝚝𝚞𝚛𝚎.", "start"),
    "fadd": ("cs_fadd",
             "𝚂𝚎𝚗𝚍 𝚝𝚑𝚎 <b>𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝙸𝙳</b> (𝚕𝚒𝚔𝚎 <code>-100\u2026</code>) 𝚘𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚊𝚗𝚢 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕.\n"
             "𝚃𝚑𝚎 𝚖𝚊𝚒𝚗 𝚋𝚘𝚝 𝚖𝚞𝚜𝚝 𝚋𝚎 𝚊𝚍𝚖𝚒𝚗 𝚝𝚑𝚎𝚛𝚎 𝚜𝚘 𝚒𝚝 𝚌𝚊𝚗 𝚊𝚍𝚍 𝚝𝚑𝚎 𝚌𝚕𝚘𝚗𝚎.", "force"),
    "madd": ("cs_madd", "𝚂𝚎𝚗𝚍 𝚝𝚑𝚎 <b>𝚞𝚜𝚎𝚛 𝙸𝙳</b> 𝚘𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚊𝚝 𝚞𝚜𝚎𝚛.", "mods"),
    "adcustom": ("cs_adcustom", "𝚂𝚎𝚗𝚍 𝚝𝚑𝚎 𝚊𝚞𝚝𝚘 𝚍𝚎𝚕𝚎𝚝𝚎 𝚝𝚒𝚖𝚎 𝚒𝚗 <b>𝚜𝚎𝚌𝚘𝚗𝚍𝚜</b> (0 = 𝚘𝚏𝚏).", "ad"),
    "toksite": ("cs_toksite", "𝚂𝚎𝚗𝚍 𝚢𝚘𝚞𝚛 𝚜𝚑𝚘𝚛𝚝𝚎𝚗𝚎𝚛 <b>𝚜𝚒𝚝𝚎</b> (𝚎.𝚐. <code>gplinks.in</code>).", "tok"),
    "tokapi": ("cs_tokapi", "𝚂𝚎𝚗𝚍 𝚢𝚘𝚞𝚛 𝚜𝚑𝚘𝚛𝚝𝚎𝚗𝚎𝚛 <b>𝙰𝙿𝙸 𝚔𝚎𝚢</b>.", "tok"),
}
SCREENS = ("menu", "start", "force", "mods", "ad", "nf", "tok", "mode", "stats", "del")


async def _cb(_, client, q):
    return bool(
        not client.is_clone and q.from_user and (q.data or "").startswith(("cs:", "mc:"))
    )


cb_filter = filters.create(_cb)


@Bot.on_callback_query(cb_filter)
async def callbacks(client, q):
    parts = q.data.split(":")
    uid = q.from_user.id
    key = (client.bot_id, uid)
    STATE.pop(key, None)  # any navigation cancels pending input

    # ----- clone list -----
    if parts[0] == "mc":
        act = parts[1]
        if act == "menu":
            await _show(q, *clones_view(client, uid))
        elif act == "add":
            if CLONE_ADMIN_ONLY and not is_admin(client, uid):
                return await q.answer("𝙾𝚗𝚕𝚢 𝚊𝚍𝚖𝚒𝚗𝚜 𝚌𝚊𝚗 𝚌𝚛𝚎𝚊𝚝𝚎 𝚌𝚕𝚘𝚗𝚎𝚜.", show_alert=True)
            STATE[key] = {"mode": "cl_token"}
            await _show(q, CLONE_HELP, M([[B("\u2b05\ufe0f 𝙱𝚊𝚌𝚔", callback_data="mc:menu")]]))
        elif act == "sel":
            t = CLONES.get(parts[2])
            if not t or not can_manage(client, t, uid):
                return await q.answer("𝙲𝚕𝚘𝚗𝚎 𝚗𝚘𝚝 𝚏𝚘𝚞𝚗𝚍.", show_alert=True)
            await _show(q, menu_text(t), menu_markup(t))
        return await q.answer()

    # ----- clone panel -----
    bot_id, act = parts[1], parts[2]
    arg = parts[3] if len(parts) > 3 else None
    t = CLONES.get(bot_id)
    if not t or not can_manage(client, t, uid):
        return await q.answer("𝙲𝚕𝚘𝚗𝚎 𝚗𝚘𝚝 𝚏𝚘𝚞𝚗𝚍 𝚘𝚛 𝚗𝚘𝚝 𝚢𝚘𝚞𝚛𝚜.", show_alert=True)
    cfg = t.cfg

    if act == "menu":
        await _show(q, menu_text(t), menu_markup(t))

    elif act in SCREENS:
        await _show(q, *await render(t, act))

    elif act in PROMPTS:
        mode, text, back_to = PROMPTS[act]
        STATE[key] = {"mode": mode, "bot": bot_id}
        await _show(q, text + "\n\n/cancel 𝚘𝚛 𝚝𝚊𝚙 𝙱𝚊𝚌𝚔 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝.",
                    M([[B("\u2b05\ufe0f 𝙱𝚊𝚌𝚔", callback_data=cd(t, back_to))]]))

    elif act == "startreset":
        cfg["start_msg"], cfg["start_pic"] = START_MESSAGE, ""
        await t.save_cfg()
        await _show(q, *await render(t, "start"))

    elif act == "fdel":
        ch = int(arg)
        if ch in cfg["force"]:
            cfg["force"].remove(ch)
            await t.save_cfg()
            await t.setup_force()
        await _show(q, *await render(t, "force"))

    elif act == "mdel":
        mid = int(arg)
        if mid in cfg["mods"]:
            cfg["mods"].remove(mid)
            await t.save_cfg()
        await _show(q, *await render(t, "mods"))

    elif act == "adset":
        cfg["auto_delete"] = int(arg)
        await t.save_cfg()
        await _show(q, *await render(t, "ad"))

    elif act == "nftoggle":
        cfg["no_forward"] = not cfg["no_forward"]
        await t.save_cfg()
        await _show(q, *await render(t, "nf"))

    elif act == "toktoggle":
        if not cfg["token_on"] and not (cfg["short_site"] and cfg["short_api"]):
            return await q.answer("𝚂𝚎𝚝 𝚝𝚑𝚎 𝚜𝚑𝚘𝚛𝚝𝚎𝚗𝚎𝚛 𝚜𝚒𝚝𝚎 & 𝙰𝙿𝙸 𝚏𝚒𝚛𝚜𝚝.", show_alert=True)
        cfg["token_on"] = not cfg["token_on"]
        await t.save_cfg()
        await _show(q, *await render(t, "tok"))

    elif act == "tokh":
        cfg["token_hours"] = int(arg)
        await t.save_cfg()
        await _show(q, *await render(t, "tok"))

    elif act == "modetoggle":
        cfg["mode"] = "private" if cfg["mode"] == "public" else "public"
        await t.save_cfg()
        await _show(q, *await render(t, "mode"))

    elif act == "deact":
        cfg["active"] = not cfg["active"]
        await t.save_cfg()
        await _show(q, menu_text(t), menu_markup(t))

    elif act == "restart":
        await _show(q, "\u267b\ufe0f <b>𝚁𝚎𝚜𝚝𝚊𝚛𝚝𝚒𝚗𝚐 𝚌𝚕𝚘𝚗𝚎...</b>", None)
        new = await restart_clone(bot_id, client)
        if new:
            await _show(q, "\u2705 <b>𝙲𝚕𝚘𝚗𝚎 𝚛𝚎𝚜𝚝𝚊𝚛𝚝𝚎𝚍.</b>\n\n" + menu_text(new), menu_markup(new))
        else:
            await _show(q, "\u274c <b>𝚁𝚎𝚜𝚝𝚊𝚛𝚝 𝚏𝚊𝚒𝚕𝚎𝚍.</b> 𝙲𝚑𝚎𝚌𝚔 𝚝𝚑𝚎 𝚕𝚘𝚐𝚜.",
                        M([[B("\u2b05\ufe0f 𝙱𝚊𝚌𝚔", callback_data="mc:menu")]]))

    elif act == "delyes":
        await stop_clone(bot_id)
        await db.del_clone(bot_id)
        await db.del_settings(bot_id)
        await db.del_bot_users(bot_id)
        await db.del_bot_files(bot_id)
        await _show(q, "\U0001f5d1 <b>𝙲𝚕𝚘𝚗𝚎 𝚍𝚎𝚕𝚎𝚝𝚎𝚍.</b>", M([[B("\u2b05\ufe0f 𝙱𝚊𝚌𝚔", callback_data="mc:menu")]]))

    await q.answer()


# ---------------- input collection ----------------

def _chan_id(message):
    txt = (message.text or "").strip()
    if re.fullmatch(r"-?\d+", txt):
        return int(txt)
    _, chat, _ = forward_info(message)
    return chat.id if chat else None


async def _probe(t, ch):
    chat = await t.get_chat(ch)
    if not chat.invite_link:
        await t.export_chat_invite_link(ch)
    return chat


async def _prep_force(main, t, ch):
    """Make sure the clone can read/invite in the channel (main bot promotes it if needed)."""
    try:
        await _probe(t, ch)
        return
    except Exception:
        pass
    await main.promote_chat_member(
        ch, int(t.bot_id), privileges=ChatPrivileges(can_manage_chat=True, can_invite_users=True)
    )
    await _probe(t, ch)


@Bot.on_message(filters.private & in_state("cs_") & ~filters.regex(r"^/"), group=1)
async def cs_input(client, message):
    key = (client.bot_id, message.from_user.id)
    st = STATE[key]
    mode = st["mode"]
    t = CLONES.get(st.get("bot"))
    if not t:
        STATE.pop(key, None)
        return await message.reply_text("\u274c 𝙲𝚕𝚘𝚗𝚎 𝚗𝚘𝚝 𝚏𝚘𝚞𝚗𝚍.")
    cfg = t.cfg
    text = (message.text or "").strip()

    async def done(msg, back):
        STATE.pop(key, None)
        await t.save_cfg()
        await message.reply_text(
            msg, quote=True, reply_markup=M([[B("\u2b05\ufe0f 𝙱𝚊𝚌𝚔", callback_data=cd(t, back))]]))

    async def fail(msg):
        await message.reply_text(f"{msg}\n\n𝚃𝚛𝚢 𝚊𝚐𝚊𝚒𝚗 𝚘𝚛 /cancel.", quote=True)

    if mode == "cs_startmsg":
        if not message.text:
            return await fail("\u274c 𝚂𝚎𝚗𝚍 𝚝𝚎𝡡𝚝.")
        cfg["start_msg"] = message.text.html
        return await done("\u2705 𝚂𝚝𝚊𝚛𝚝 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚞𝚙𝚍𝚊𝚝𝚎𝚍.", "start")

    if mode == "cs_startpic":
        if not text.lower().startswith(("http://", "https://")):
            return await fail("\u274c 𝚂𝚎𝚗𝚍 𝚊 𝚍𝚒𝚛𝚎𝚌𝚝 𝚒𝚖𝚊𝚐𝚎 𝚄𝚁𝙻 𝚜𝚝𝚊𝚛𝚝𝚒𝚗𝚐 𝚠𝚒𝚝𝚑 https://")
        cfg["start_pic"] = text
        return await done("\u2705 𝚂𝚝𝚊𝚛𝚝 𝚙𝚒𝚌𝚝𝚞𝚛𝚎 𝚞𝚙𝚍𝚊𝚝𝚎𝚍.", "start")

    if mode == "cs_fadd":
        ch = _chan_id(message)
        if ch is None:
            return await fail("\u274c 𝚂𝚎𝚗𝚍 𝚊 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝙸𝙳 𝚘𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕.")
        if ch in cfg["force"]:
            return await fail("\u274c 𝚃𝚑𝚊𝚝 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚒𝚜 𝚊𝚕𝚛𝚎𝚊𝚍𝚢 𝚊𝚍𝚍𝚎𝚍.")
        if len(cfg["force"]) >= 4:
            return await fail("\u274c 𝙼𝚊𝡡𝚒𝚖𝚞𝚖 4 𝚏𝚘𝚛𝚌𝚎 𝚜𝚞𝚋 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜.")
        try:
            await _prep_force(client, t, ch)
        except Exception as e:
            return await fail(f"\u274c 𝙲𝚊𝚗'𝚝 𝚞𝚜𝚎 𝚝𝚑𝚊𝚝 𝚌𝚑𝚊𝚗𝚗𝚎𝚕: <code>{e}</code>\n"
                              "𝙼𝚊𝚔𝚎 𝚝𝚑𝚎 𝚖𝚊𝚒𝚗 𝚋𝚘𝚝 (𝚠𝚒𝚝𝚑 𝚊𝚍𝚍-𝚊𝚍𝚖𝚒𝚗 𝚛𝚒𝚐𝚑𝚝𝚜) 𝚘𝚛 𝚝𝚑𝚎 𝚌𝚕𝚘𝚗𝚎 𝚊𝚍𝚖𝚒𝚗 𝚝𝚑𝚎𝚛𝚎.")
        cfg["force"].append(ch)
        await t.setup_force()
        return await done("\u2705 𝙵𝚘𝚛𝚌𝚎 𝚜𝚞𝚋 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚊𝚍𝚍𝚎𝚍.", "force")

    if mode == "cs_madd":
        new = None
        if text.lstrip("-").isdigit():
            new = int(text)
        else:
            origin = getattr(message, "forward_origin", None)
            u = getattr(origin, "sender_user", None) or getattr(message, "forward_from", None)
            if u:
                new = u.id
        if not new:
            return await fail("\u274c 𝚂𝚎𝚗𝚍 𝚊 𝚗𝚞𝚖𝚎𝚛𝚒𝚌 𝚞𝚜𝚎𝚛 𝙸𝙳 𝚘𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚞𝚜𝚎𝚛.")
        if new not in cfg["mods"]:
            cfg["mods"].append(new)
        return await done("\u2705 𝙼𝚘𝚍𝚎𝚛𝚊𝚝𝚘𝚛 𝚊𝚍𝚍𝚎𝚍.", "mods")

    if mode == "cs_adcustom":
        if not text.isdigit():
            return await fail("\u274c 𝚂𝚎𝚗𝚍 𝚊 𝚗𝚞𝚖𝚋𝚎𝚛 𝚘𝚏 𝚜𝚎𝚌𝚘𝚗𝚍𝚜.")
        cfg["auto_delete"] = int(text)
        return await done("\u2705 𝙰𝚞𝚝𝚘 𝚍𝚎𝚕𝚎𝚝𝚎 𝚞𝚙𝚍𝚊𝚝𝚎𝚍.", "ad")

    if mode == "cs_toksite":
        site = text.replace("https://", "").replace("http://", "").strip("/")
        if not site or " " in site:
            return await fail("\u274c 𝚂𝚎𝚗𝚍 𝚊 𝚟𝚊𝚕𝚒𝚍 𝚜𝚒𝚝𝚎 𝚕𝚒𝚔𝚎 <code>gplinks.in</code>.")
        cfg["short_site"] = site
        return await done("\u2705 𝚂𝚑𝚘𝚛𝚝𝚎𝚗𝚎𝚛 𝚜𝚒𝚝𝚎 𝚜𝚊𝚟𝚎𝚍.", "tok")

    if mode == "cs_tokapi":
        if not text:
            return await fail("\u274c 𝚂𝚎𝚗𝚍 𝚝𝚑𝚎 𝙰𝙿𝙸 𝚔𝚎𝚢 𝚊𝚜 𝚝𝚎𝡡𝚝.")
        cfg["short_api"] = text
        try:
            await message.delete()  # hide the key
        except Exception:
            pass
        return await done("\u2705 𝚂𝚑𝚘𝚛𝚝𝚎𝚗𝚎𝚛 𝙰𝙿𝙸 𝚜𝚊𝚟𝚎𝚍.", "tok")

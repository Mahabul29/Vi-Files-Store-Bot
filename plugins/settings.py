"""Customize Clone panel (clone owner only)."""
import asyncio
import html
import re
from datetime import datetime

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from bot import Bot, restart_clone, stop_clone
from config import START_MESSAGE
from database.database import db
from helper_func import START_BUTTONS, fill, forward_info, get_readable_time
from state import STATE, in_state


# ---------------- filters ----------------

async def _owner_cb(_, client, q):
    return bool(
        client.is_clone and q.from_user and q.from_user.id == client.owner_id
        and (q.data or "").startswith("cs:")
    )


async def _owner_msg(_, client, m):
    return bool(client.is_clone and m.from_user and m.from_user.id == client.owner_id)


owner_cb = filters.create(_owner_cb)
owner_msg = filters.create(_owner_msg)


# ---------------- views ----------------

def _onoff(v):
    return "ON âœ…" if v else "OFF âŒ"


def menu_text(client):
    t = (
        "ðŸª„ <u><b>Customize Clone</b></u>\n\n"
        f"âž› <b>Name:</b> {html.escape(client.display_name or '')}\n\n"
        "<i>Configure Your Clone Settings Using Given Buttons</i>"
    )
    if not client.cfg["db_channel"]:
        t += "\n\nâš ï¸ <b>DB channel not set.</b> Tap TRANSFER DB to set it."
    return t


def menu_markup(client):
    active = client.cfg["active"]
    return M([
        [B("START MSG", callback_data="cs:start"), B("FORCE SUB", callback_data="cs:force")],
        [B("MODERATORS", callback_data="cs:mods"), B("AUTO DELETE", callback_data="cs:ad")],
        [B("NO FORWARD", callback_data="cs:nf"), B("ACCESS TOKEN", callback_data="cs:tok")],
        [B("TRANSFER DB", callback_data="cs:db"),
         B("DEACTIVATE" if active else "ACTIVATE", callback_data="cs:deact")],
        [B("MODE", callback_data="cs:mode"), B("RESTART", callback_data="cs:restart")],
        [B("STATS", callback_data="cs:stats"), B("DELETE", callback_data="cs:del")],
        [B("BACK", callback_data="cs:back")],
    ])


async def render(client, name):
    cfg = client.cfg
    back = [B("â¬…ï¸ Back", callback_data="cs:menu")]

    if name == "menu":
        return menu_text(client), menu_markup(client)

    if name == "start":
        pic = "set âœ…" if cfg["start_pic"] else "not set"
        return (
            f"ðŸ“ <b>Start Message</b>\n\n{cfg['start_msg']}\n\nðŸ–¼ Picture: {pic}",
            M([[B("âœï¸ Set Message", callback_data="cs:startmsg"),
                B("ðŸ–¼ Set Picture", callback_data="cs:startpic")],
               [B("â™»ï¸ Reset", callback_data="cs:startreset")], back]),
        )

    if name == "force":
        rows = [[B(f"âŒ {client.fsub_titles.get(ch, ch)}", callback_data=f"cs:fdel:{ch}")]
                for ch in cfg["force"]]
        if len(cfg["force"]) < 4:
            rows.append([B("âž• Add Channel", callback_data="cs:fadd")])
        rows.append(back)
        return (
            f"ðŸ“¢ <b>Force Sub</b> ({len(cfg['force'])}/4)\n\n"
            "Users must join these channels before getting files.\nTap a channel to remove it.",
            M(rows),
        )

    if name == "mods":
        rows = [[B(f"âŒ {m}", callback_data=f"cs:mdel:{m}")] for m in cfg["mods"]]
        rows.append([B("âž• Add Moderator", callback_data="cs:madd")])
        rows.append(back)
        return (
            "ðŸ‘® <b>Moderators</b>\n\nModerators can create links (/genlink, /batch) and use admin commands.\n"
            "Tap an ID to remove it.",
            M(rows),
        )

    if name == "ad":
        cur = int(cfg["auto_delete"])
        return (
            f"ðŸ—‘ <b>Auto Delete</b>\n\nCurrent: <b>{get_readable_time(cur) if cur else 'OFF'}</b>\n\n"
            "Delivered files are deleted from the user's chat after this time.",
            M([[B("OFF", callback_data="cs:adset:0"), B("5 min", callback_data="cs:adset:300"),
                B("10 min", callback_data="cs:adset:600")],
               [B("30 min", callback_data="cs:adset:1800"), B("1 hour", callback_data="cs:adset:3600"),
                B("âœï¸ Custom", callback_data="cs:adcustom")], back]),
        )

    if name == "nf":
        on = cfg["no_forward"]
        return (
            f"ðŸš« <b>No Forward</b>\n\nStatus: <b>{_onoff(on)}</b>\n\nWhen ON, files can't be forwarded or saved.",
            M([[B("Turn OFF" if on else "Turn ON", callback_data="cs:nftoggle")], back]),
        )

    if name == "tok":
        api = cfg["short_api"]
        masked = ("â€¢â€¢â€¢" + api[-4:]) if api else "not set"
        on = cfg["token_on"]
        return (
            "ðŸ”‘ <b>Access Token</b>\n\n"
            f"Status: <b>{_onoff(on)}</b>\n"
            f"Shortener: <code>{html.escape(cfg['short_site'] or 'not set')}</code>\n"
            f"API: <code>{masked}</code>\n"
            f"Validity: <b>{cfg['token_hours']}h</b>\n\n"
            "Users verify through your shortener link to unlock files for the validity period.",
            M([[B("Turn OFF" if on else "Turn ON", callback_data="cs:toktoggle")],
               [B("ðŸŒ Set Site", callback_data="cs:toksite"), B("ðŸ”‘ Set API", callback_data="cs:tokapi")],
               [B("6h", callback_data="cs:tokh:6"), B("12h", callback_data="cs:tokh:12"),
                B("24h", callback_data="cs:tokh:24"), B("48h", callback_data="cs:tokh:48")], back]),
        )

    if name == "db":
        return (
            f"ðŸ—„ <b>Transfer DB</b>\n\nCurrent DB channel: <code>{cfg['db_channel'] or 'not set'}</code>\n\n"
            "âš ï¸ Links made with the old channel stop working after a change.",
            M([[B("ðŸ”„ Set New DB Channel", callback_data="cs:dbset")], back]),
        )

    if name == "mode":
        m = cfg["mode"]
        return (
            f"ðŸ” <b>Mode</b>\n\nCurrent: <b>{m.upper()}</b>\n\n"
            "â€¢ PUBLIC â€“ anyone with a link can get files\n"
            "â€¢ PRIVATE â€“ only you and moderators can get files",
            M([[B("Switch to PRIVATE" if m == "public" else "Switch to PUBLIC",
                  callback_data="cs:modetoggle")], back]),
        )

    if name == "stats":
        users = await db.count_users(client.bot_id)
        up = get_readable_time((datetime.now() - client.uptime).total_seconds())
        ad = int(cfg["auto_delete"])
        return (
            "ðŸ“Š <b>Stats</b>\n\n"
            f"ðŸ‘¥ Users: <b>{users}</b>\n"
            f"â± Uptime: <b>{up}</b>\n"
            f"âš¡ Status: <b>{'Active' if cfg['active'] else 'Deactivated'}</b>\n"
            f"ðŸ” Mode: <b>{cfg['mode'].upper()}</b>\n"
            f"ðŸ“¢ Force sub: <b>{len(client.force_channels)}</b>\n"
            f"ðŸ‘® Moderators: <b>{len(cfg['mods'])}</b>\n"
            f"ðŸ—‘ Auto delete: <b>{get_readable_time(ad) if ad else 'OFF'}</b>\n"
            f"ðŸš« No forward: <b>{_onoff(cfg['no_forward'])}</b>\n"
            f"ðŸ”‘ Access token: <b>{_onoff(cfg['token_on'])}</b>",
            M([back]),
        )

    if name == "del":
        return (
            "âš ï¸ <b>Delete this clone?</b>\n\nThis removes the clone and all its data permanently.",
            M([[B("âœ… Yes, delete", callback_data="cs:delyes"), B("âŒ No", callback_data="cs:menu")]]),
        )

    return menu_text(client), menu_markup(client)


async def _show(q, text, markup):
    try:
        await q.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass


# ---------------- commands ----------------

@Bot.on_message(filters.private & filters.command("settings") & owner_msg)
async def settings_cmd(client, message):
    await message.reply_text(
        menu_text(client), reply_markup=menu_markup(client),
        disable_web_page_preview=True, quote=True,
    )


# ---------------- callbacks ----------------

PROMPTS = {
    "startmsg": ("cs_startmsg",
                 "Send the new <b>start message</b> (HTML allowed).\n"
                 "Fillings: <code>{first} {last} {username} {mention} {id}</code>", "start"),
    "startpic": ("cs_startpic", "Send the <b>photo</b> to use as the start picture.", "start"),
    "fadd": ("cs_fadd",
             "Send the <b>channel ID</b> (like <code>-100â€¦</code>) or forward any message from the channel.\n"
             "The bot must be admin there (invite-link permission).", "force"),
    "madd": ("cs_madd", "Send the <b>user ID</b> or forward a message from that user.", "mods"),
    "adcustom": ("cs_adcustom", "Send the auto delete time in <b>seconds</b> (0 = off).", "ad"),
    "toksite": ("cs_toksite", "Send your shortener <b>site</b> (e.g. <code>gplinks.in</code>).", "tok"),
    "tokapi": ("cs_tokapi", "Send your shortener <b>API key</b>.", "tok"),
    "dbset": ("cs_dbset",
              "âš ï¸ Old links stop working after changing the DB channel.\n\n"
              "Send the new <b>DB channel ID</b> or forward a message from it.\n"
              "The bot must be admin with post rights.", "db"),
}


@Bot.on_callback_query(owner_cb)
async def cs_callback(client, q):
    parts = q.data.split(":")
    act = parts[1]
    arg = parts[2] if len(parts) > 2 else None
    cfg = client.cfg
    key = (client.bot_id, q.from_user.id)
    STATE.pop(key, None)  # any navigation cancels pending input

    if act in ("menu", "start", "force", "mods", "ad", "nf", "tok", "db", "mode", "stats", "del"):
        text, markup = await render(client, act)
        await _show(q, text, markup)

    elif act in PROMPTS:
        mode, text, back_to = PROMPTS[act]
        STATE[key] = {"mode": mode}
        await _show(q, text + "\n\n/cancel or tap Back to abort.",
                    M([[B("â¬…ï¸ Back", callback_data=f"cs:{back_to}")]]))

    elif act == "startreset":
        cfg["start_msg"], cfg["start_pic"] = START_MESSAGE, ""
        await client.save_cfg()
        await _show(q, *await render(client, "start"))

    elif act == "fdel":
        ch = int(arg)
        if ch in cfg["force"]:
            cfg["force"].remove(ch)
            await client.save_cfg()
            await client.setup_force()
        await _show(q, *await render(client, "force"))

    elif act == "mdel":
        uid = int(arg)
        if uid in cfg["mods"]:
            cfg["mods"].remove(uid)
            await client.save_cfg()
        await _show(q, *await render(client, "mods"))

    elif act == "adset":
        cfg["auto_delete"] = int(arg)
        await client.save_cfg()
        await _show(q, *await render(client, "ad"))

    elif act == "nftoggle":
        cfg["no_forward"] = not cfg["no_forward"]
        await client.save_cfg()
        await _show(q, *await render(client, "nf"))

    elif act == "toktoggle":
        if not cfg["token_on"] and not (cfg["short_site"] and cfg["short_api"]):
            return await q.answer("Set the shortener site & API first.", show_alert=True)
        cfg["token_on"] = not cfg["token_on"]
        await client.save_cfg()
        await _show(q, *await render(client, "tok"))

    elif act == "tokh":
        cfg["token_hours"] = int(arg)
        await client.save_cfg()
        await _show(q, *await render(client, "tok"))

    elif act == "modetoggle":
        cfg["mode"] = "private" if cfg["mode"] == "public" else "public"
        await client.save_cfg()
        await _show(q, *await render(client, "mode"))

    elif act == "deact":
        cfg["active"] = not cfg["active"]
        await client.save_cfg()
        await _show(q, *await render(client, "menu"))

    elif act == "restart":
        await _show(q, "â™»ï¸ <b>Restarting clone...</b>", None)
        asyncio.create_task(restart_clone(client.bot_id))

    elif act == "delyes":
        bot_id = client.bot_id
        await db.del_clone(bot_id)
        await db.del_settings(bot_id)
        await db.del_bot_users(bot_id)
        await _show(q, "ðŸ—‘ <b>Clone deleted.</b>", None)
        asyncio.create_task(stop_clone(bot_id))

    elif act == "back":
        try:
            await q.message.edit_text(
                fill(cfg["start_msg"], q.from_user), reply_markup=START_BUTTONS,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

    await q.answer()


# ---------------- input collection ----------------

def _chan_id(message):
    t = (message.text or "").strip()
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    _, chat, _ = forward_info(message)
    return chat.id if chat else None


@Bot.on_message(filters.private & owner_msg & in_state("cs_") & ~filters.regex(r"^/"), group=1)
async def cs_input(client, message):
    key = (client.bot_id, message.from_user.id)
    mode = STATE[key]["mode"]
    cfg = client.cfg
    text = (message.text or "").strip()

    async def done(msg, back):
        STATE.pop(key, None)
        await client.save_cfg()
        await message.reply_text(
            msg, quote=True, reply_markup=M([[B("â¬…ï¸ Back", callback_data=f"cs:{back}")]]))

    async def fail(msg):
        await message.reply_text(f"{msg}\n\nTry again or /cancel.", quote=True)

    if mode == "cs_startmsg":
        if not message.text:
            return await fail("âŒ Send text.")
        cfg["start_msg"] = message.text.html
        return await done("âœ… Start message updated.", "start")

    if mode == "cs_startpic":
        if not message.photo:
            return await fail("âŒ Send a photo.")
        cfg["start_pic"] = message.photo.file_id
        return await done("âœ… Start picture updated.", "start")

    if mode == "cs_fadd":
        ch = _chan_id(message)
        if ch is None:
            return await fail("âŒ Send a channel ID or forward a message from the channel.")
        if ch in cfg["force"]:
            return await fail("âŒ That channel is already added.")
        if len(cfg["force"]) >= 4:
            return await fail("âŒ Maximum 4 force sub channels.")
        try:
            chat = await client.get_chat(ch)
            if not chat.invite_link:
                await client.export_chat_invite_link(ch)
        except Exception as e:
            return await fail(f"âŒ Can't use that channel: <code>{e}</code>\n"
                              "Make the bot admin with invite-link permission.")
        cfg["force"].append(ch)
        await client.setup_force()
        return await done("âœ… Force sub channel added.", "force")

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
            return await fail("âŒ Send a numeric user ID or forward a message from the user.")
        if new not in cfg["mods"]:
            cfg["mods"].append(new)
        return await done("âœ… Moderator added.", "mods")

    if mode == "cs_adcustom":
        if not text.isdigit():
            return await fail("âŒ Send a number of seconds.")
        cfg["auto_delete"] = int(text)
        return await done("âœ… Auto delete updated.", "ad")

    if mode == "cs_toksite":
        site = text.replace("https://", "").replace("http://", "").strip("/")
        if not site or " " in site:
            return await fail("âŒ Send a valid site like <code>gplinks.in</code>.")
        cfg["short_site"] = site
        return await done("âœ… Shortener site saved.", "tok")

    if mode == "cs_tokapi":
        if not text:
            return await fail("âŒ Send the API key as text.")
        cfg["short_api"] = text
        try:
            await message.delete()  # hide the key
        except Exception:
            pass
        return await done("âœ… Shortener API saved.", "tok")

    if mode == "cs_dbset":
        ch = _chan_id(message)
        if ch is None:
            return await fail("âŒ Send a channel ID or forward a message from the channel.")
        try:
            chat = await client.get_chat(ch)
            test = await client.send_message(chat.id, "Test Message")
            await test.delete()
        except Exception as e:
            return await fail(f"âŒ Can't use that channel: <code>{e}</code>\n"
                              "Make the bot admin with post rights.")
        cfg["db_channel"] = chat.id
        client.db_channel = chat
        return await done("âœ… DB channel updated. Make new links with /genlink or /batch.", "menu")

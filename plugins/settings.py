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
    "<b>🤖 Create your own clone</b>\n\n"
    "1. Open @BotFather and create a bot with /newbot\n"
    "2. Copy the bot token\n"
    "3. Send it here (or forward BotFather's message)\n\n"
    "/cancel to abort."
)


def cd(t, act, arg=None):
    return f"cs:{t.bot_id}:{act}" + (f":{arg}" if arg is not None else "")


def can_manage(client, t, uid):
    return uid == t.owner_id or is_admin(client, uid)


# ---------------- clone list ----------------

def clones_view(client, uid):
    mine = [c for c in CLONES.values() if can_manage(client, c, uid)]
    rows = [[B(f"🤖 @{c.username}", callback_data=f"mc:sel:{c.bot_id}")] for c in mine]
    rows.append([B("➕ Add Clone", callback_data="mc:add")])
    text = "🤖 <b>Your Clones</b>\n\n" + (
        "Select a clone to customize it." if mine else "You don't have any clones yet."
    )
    return text, M(rows)


# ---------------- panel ----------------

def _onoff(v):
    return "ON ✅" if v else "OFF ❌"


def menu_text(t):
    text = (
        "🪄 <u><b>Customize Clone</b></u>\n\n"
        f"➛ <b>Name:</b> {html.escape(t.display_name or '')}\n\n"
        "<i>Configure Your Clone Settings Using Given Buttons</i>"
    )
    if not t.db_channel:
        text += ("\n\n⚠️ <b>This clone can't access the main DB channel yet.</b> "
                 "Add it as admin there, then tap RESTART.")
    return text


def menu_markup(t):
    return M([
        [B("START MSG", callback_data=cd(t, "start")), B("FORCE SUB", callback_data=cd(t, "force"))],
        [B("MODERATORS", callback_data=cd(t, "mods")), B("AUTO DELETE", callback_data=cd(t, "ad"))],
        [B("NO FORWARD", callback_data=cd(t, "nf")), B("ACCESS TOKEN", callback_data=cd(t, "tok"))],
        [B("DEACTIVATE" if t.cfg["active"] else "ACTIVATE", callback_data=cd(t, "deact")),
         B("MODE", callback_data=cd(t, "mode"))],
        [B("RESTART", callback_data=cd(t, "restart")), B("STATS", callback_data=cd(t, "stats"))],
        [B("DELETE", callback_data=cd(t, "del"))],
        [B("BACK", callback_data="mc:menu")],
    ])


async def render(t, name):
    cfg = t.cfg
    back = [B("⬅️ Back", callback_data=cd(t, "menu"))]

    if name == "start":
        pic = "set ✅" if cfg["start_pic"] else "not set"
        return (
            f"📝 <b>Start Message</b>\n\n{cfg['start_msg']}\n\n🖼 Picture: {pic}",
            M([[B("✏️ Set Message", callback_data=cd(t, "startmsg")),
                B("🖼 Set Picture", callback_data=cd(t, "startpic"))],
               [B("♻️ Reset", callback_data=cd(t, "startreset"))], back]),
        )

    if name == "force":
        rows = [[B(f"❌ {t.fsub_titles.get(ch, ch)}", callback_data=cd(t, "fdel", ch))]
                for ch in cfg["force"]]
        if len(cfg["force"]) < 4:
            rows.append([B("➕ Add Channel", callback_data=cd(t, "fadd"))])
        rows.append(back)
        return (
            f"📢 <b>Force Sub</b> ({len(cfg['force'])}/4)\n\n"
            "Users must join these channels before getting files.\nTap a channel to remove it.",
            M(rows),
        )

    if name == "mods":
        rows = [[B(f"❌ {m}", callback_data=cd(t, "mdel", m))] for m in cfg["mods"]]
        rows.append([B("➕ Add Moderator", callback_data=cd(t, "madd"))])
        rows.append(back)
        return (
            "👮 <b>Moderators</b>\n\nModerators can store files in the clone and use its admin commands.\n"
            "Tap an ID to remove it.",
            M(rows),
        )

    if name == "ad":
        cur = int(cfg["auto_delete"])
        return (
            f"🗑 <b>Auto Delete</b>\n\nCurrent: <b>{get_readable_time(cur) if cur else 'OFF'}</b>\n\n"
            "Delivered files are deleted from the user's chat after this time.",
            M([[B("OFF", callback_data=cd(t, "adset", 0)), B("5 min", callback_data=cd(t, "adset", 300)),
                B("10 min", callback_data=cd(t, "adset", 600))],
               [B("30 min", callback_data=cd(t, "adset", 1800)), B("1 hour", callback_data=cd(t, "adset", 3600)),
                B("✏️ Custom", callback_data=cd(t, "adcustom"))], back]),
        )

    if name == "nf":
        on = cfg["no_forward"]
        return (
            f"🚫 <b>No Forward</b>\n\nStatus: <b>{_onoff(on)}</b>\n\nWhen ON, files can't be forwarded or saved.",
            M([[B("Turn OFF" if on else "Turn ON", callback_data=cd(t, "nftoggle"))], back]),
        )

    if name == "tok":
        api = cfg["short_api"]
        masked = ("•••" + api[-4:]) if api else "not set"
        on = cfg["token_on"]
        return (
            "🔑 <b>Access Token</b>\n\n"
            f"Status: <b>{_onoff(on)}</b>\n"
            f"Shortener: <code>{html.escape(cfg['short_site'] or 'not set')}</code>\n"
            f"API: <code>{masked}</code>\n"
            f"Validity: <b>{cfg['token_hours']}h</b>\n\n"
            "Users verify through your shortener link to unlock files for the validity period.",
            M([[B("Turn OFF" if on else "Turn ON", callback_data=cd(t, "toktoggle"))],
               [B("🌐 Set Site", callback_data=cd(t, "toksite")), B("🔑 Set API", callback_data=cd(t, "tokapi"))],
               [B("6h", callback_data=cd(t, "tokh", 6)), B("12h", callback_data=cd(t, "tokh", 12)),
                B("24h", callback_data=cd(t, "tokh", 24)), B("48h", callback_data=cd(t, "tokh", 48))], back]),
        )

    if name == "mode":
        m = cfg["mode"]
        return (
            f"🔁 <b>Mode</b>\n\nCurrent: <b>{m.upper()}</b>\n\n"
            "• PUBLIC – anyone with a link can get files\n"
            "• PRIVATE – only the owner and moderators can get files",
            M([[B("Switch to PRIVATE" if m == "public" else "Switch to PUBLIC",
                  callback_data=cd(t, "modetoggle"))], back]),
        )

    if name == "stats":
        users = await db.count_users(t.bot_id)
        up = get_readable_time((datetime.now() - t.uptime).total_seconds())
        ad = int(cfg["auto_delete"])
        return (
            "📊 <b>Stats</b>\n\n"
            f"🤖 Bot: @{t.username}\n"
            f"👥 Users: <b>{users}</b>\n"
            f"⏱ Uptime: <b>{up}</b>\n"
            f"⚡ Status: <b>{'Active' if cfg['active'] else 'Deactivated'}</b>\n"
            f"🗄 Main DB access: <b>{'✅' if t.db_channel else '❌'}</b>\n"
            f"🔁 Mode: <b>{cfg['mode'].upper()}</b>\n"
            f"📢 Force sub: <b>{len(t.force_channels)}</b>\n"
            f"👮 Moderators: <b>{len(cfg['mods'])}</b>\n"
            f"🗑 Auto delete: <b>{get_readable_time(ad) if ad else 'OFF'}</b>\n"
            f"🚫 No forward: <b>{_onoff(cfg['no_forward'])}</b>\n"
            f"🔑 Access token: <b>{_onoff(cfg['token_on'])}</b>",
            M([back]),
        )

    if name == "del":
        return (
            "⚠️ <b>Delete this clone?</b>\n\nThis removes the clone and all its data permanently.",
            M([[B("✅ Yes, delete", callback_data=cd(t, "delyes")), B("❌ No", callback_data=cd(t, "menu"))]]),
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
                 "Send the new <b>start message</b> (HTML allowed).\n"
                 "Fillings: <code>{first} {last} {username} {mention} {id}</code>", "start"),
    "startpic": ("cs_startpic", "Send a direct <b>image URL</b> (https://…) to use as the start picture.", "start"),
    "fadd": ("cs_fadd",
             "Send the <b>channel ID</b> (like <code>-100…</code>) or forward any message from the channel.\n"
             "The main bot must be admin there so it can add the clone.", "force"),
    "madd": ("cs_madd", "Send the <b>user ID</b> or forward a message from that user.", "mods"),
    "adcustom": ("cs_adcustom", "Send the auto delete time in <b>seconds</b> (0 = off).", "ad"),
    "toksite": ("cs_toksite", "Send your shortener <b>site</b> (e.g. <code>gplinks.in</code>).", "tok"),
    "tokapi": ("cs_tokapi", "Send your shortener <b>API key</b>.", "tok"),
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
                return await q.answer("Only admins can create clones.", show_alert=True)
            STATE[key] = {"mode": "cl_token"}
            await _show(q, CLONE_HELP, M([[B("⬅️ Back", callback_data="mc:menu")]]))
        elif act == "sel":
            t = CLONES.get(parts[2])
            if not t or not can_manage(client, t, uid):
                return await q.answer("Clone not found.", show_alert=True)
            await _show(q, menu_text(t), menu_markup(t))
        return await q.answer()

    # ----- clone panel -----
    bot_id, act = parts[1], parts[2]
    arg = parts[3] if len(parts) > 3 else None
    t = CLONES.get(bot_id)
    if not t or not can_manage(client, t, uid):
        return await q.answer("Clone not found or not yours.", show_alert=True)
    cfg = t.cfg

    if act == "menu":
        await _show(q, menu_text(t), menu_markup(t))

    elif act in SCREENS:
        await _show(q, *await render(t, act))

    elif act in PROMPTS:
        mode, text, back_to = PROMPTS[act]
        STATE[key] = {"mode": mode, "bot": bot_id}
        await _show(q, text + "\n\n/cancel or tap Back to abort.",
                    M([[B("⬅️ Back", callback_data=cd(t, back_to))]]))

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
            return await q.answer("Set the shortener site & API first.", show_alert=True)
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
        await _show(q, "♻️ <b>Restarting clone...</b>", None)
        new = await restart_clone(bot_id, client)
        if new:
            await _show(q, "✅ <b>Clone restarted.</b>\n\n" + menu_text(new), menu_markup(new))
        else:
            await _show(q, "❌ <b>Restart failed.</b> Check the logs.",
                        M([[B("⬅️ Back", callback_data="mc:menu")]]))

    elif act == "delyes":
        await stop_clone(bot_id)
        await db.del_clone(bot_id)
        await db.del_settings(bot_id)
        await db.del_bot_users(bot_id)
        await db.del_bot_files(bot_id)
        await _show(q, "🗑 <b>Clone deleted.</b>", M([[B("⬅️ Back", callback_data="mc:menu")]]))

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
        return await message.reply_text("❌ Clone not found.")
    cfg = t.cfg
    text = (message.text or "").strip()

    async def done(msg, back):
        STATE.pop(key, None)
        await t.save_cfg()
        await message.reply_text(
            msg, quote=True, reply_markup=M([[B("⬅️ Back", callback_data=cd(t, back))]]))

    async def fail(msg):
        await message.reply_text(f"{msg}\n\nTry again or /cancel.", quote=True)

    if mode == "cs_startmsg":
        if not message.text:
            return await fail("❌ Send text.")
        cfg["start_msg"] = message.text.html
        return await done("✅ Start message updated.", "start")

    if mode == "cs_startpic":
        if not text.lower().startswith(("http://", "https://")):
            return await fail("❌ Send a direct image URL starting with https://")
        cfg["start_pic"] = text
        return await done("✅ Start picture updated.", "start")

    if mode == "cs_fadd":
        ch = _chan_id(message)
        if ch is None:
            return await fail("❌ Send a channel ID or forward a message from the channel.")
        if ch in cfg["force"]:
            return await fail("❌ That channel is already added.")
        if len(cfg["force"]) >= 4:
            return await fail("❌ Maximum 4 force sub channels.")
        try:
            await _prep_force(client, t, ch)
        except Exception as e:
            return await fail(f"❌ Can't use that channel: <code>{e}</code>\n"
                              "Make the main bot (with add-admin rights) or the clone admin there.")
        cfg["force"].append(ch)
        await t.setup_force()
        return await done("✅ Force sub channel added.", "force")

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
            return await fail("❌ Send a numeric user ID or forward a message from the user.")
        if new not in cfg["mods"]:
            cfg["mods"].append(new)
        return await done("✅ Moderator added.", "mods")

    if mode == "cs_adcustom":
        if not text.isdigit():
            return await fail("❌ Send a number of seconds.")
        cfg["auto_delete"] = int(text)
        return await done("✅ Auto delete updated.", "ad")

    if mode == "cs_toksite":
        site = text.replace("https://", "").replace("http://", "").strip("/")
        if not site or " " in site:
            return await fail("❌ Send a valid site like <code>gplinks.in</code>.")
        cfg["short_site"] = site
        return await done("✅ Shortener site saved.", "tok")

    if mode == "cs_tokapi":
        if not text:
            return await fail("❌ Send the API key as text.")
        cfg["short_api"] = text
        try:
            await message.delete()  # hide the key
        except Exception:
            pass
        return await done("✅ Shortener API saved.", "tok")
        

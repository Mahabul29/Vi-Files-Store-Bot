import asyncio
from datetime import datetime

from pyrogram import filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import Bot
from config import (
    ADMINS, CHANNEL_ID, FILE_AUTO_DELETE, FORCE_PIC, FORCE_SUB_MESSAGE,
    PROTECT_CONTENT, START_MESSAGE, START_PIC,
)
from database.database import db
from helper_func import decode, get_messages, get_readable_time, get_unjoined, subscribed

START_BUTTONS = InlineKeyboardMarkup(
    [[InlineKeyboardButton("ðŸ˜Š About Me", callback_data="about"),
      InlineKeyboardButton("ðŸ”’ Close", callback_data="close")]]
)


def fill(template, user):
    return template.format(
        first=user.first_name,
        last=user.last_name,
        username=None if not user.username else "@" + user.username,
        mention=user.mention,
        id=user.id,
    )


async def _reply(message, text, markup, pic):
    if pic:
        try:
            return await message.reply_photo(photo=pic, caption=text, reply_markup=markup, quote=True)
        except Exception:
            pass
    return await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True, quote=True)


async def _auto_delete(sent, notice, link, delay):
    await asyncio.sleep(delay)
    for m in sent:
        try:
            await m.delete()
        except Exception:
            pass
    try:
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("â™»ï¸ Get Files Again", url=link)]]) if link else None
        await notice.edit_text("<b>ðŸ—‘ Your files were deleted. Tap below to get them again.</b>", reply_markup=markup)
    except Exception:
        pass


@Bot.on_message(filters.command("start") & filters.private & subscribed)
async def start_command(client, message):
    user = message.from_user
    await db.add_user(user.id)

    if len(message.command) > 1:
        try:
            argument = (await decode(message.command[1])).split("-")
            abs_ch = abs(CHANNEL_ID)
            if len(argument) == 3 and argument[0] == "get":
                s, e = int(argument[1]) // abs_ch, int(argument[2]) // abs_ch
                ids = list(range(s, e + 1)) if s <= e else list(range(s, e - 1, -1))
            elif len(argument) == 2 and argument[0] == "get":
                ids = [int(argument[1]) // abs_ch]
            else:
                return
        except Exception:
            return await message.reply_text("âŒ Invalid or broken link.", quote=True)

        temp = await message.reply_text("â³ Please wait...", quote=True)
        msgs = await get_messages(client, ids)
        if not msgs:
            return await temp.edit_text("âŒ Files not found or deleted.")
        await temp.delete()

        sent = []
        for msg in msgs:
            caption = msg.caption.html if msg.caption else ""
            try:
                sent.append(await msg.copy(
                    user.id, caption=caption, protect_content=PROTECT_CONTENT, reply_markup=None
                ))
                await asyncio.sleep(0.4)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    sent.append(await msg.copy(
                        user.id, caption=caption, protect_content=PROTECT_CONTENT, reply_markup=None
                    ))
                except Exception:
                    pass
            except Exception:
                pass

        delay = int(await db.get_setting("auto_delete", FILE_AUTO_DELETE))
        if delay > 0 and sent:
            link = f"https://t.me/{client.username}?start={message.command[1]}"
            notice = await message.reply_text(
                f"<b>âš ï¸ These files will be deleted in {get_readable_time(delay)}. "
                "Forward them somewhere safe now.</b>"
            )
            asyncio.create_task(_auto_delete(sent, notice, link, delay))
        return

    await _reply(message, fill(START_MESSAGE, user), START_BUTTONS, START_PIC)


@Bot.on_message(filters.command("start") & filters.private)
async def not_joined(client, message):
    missing = await get_unjoined(client, message.from_user.id)
    if not missing:
        return await start_command(client, message)

    rows, row = [], []
    for i, ch in enumerate(missing, 1):
        row.append(InlineKeyboardButton(f"ðŸ“¢ Join Channel {i}", url=client.invitelinks[ch]))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if len(message.command) > 1:
        rows.append([InlineKeyboardButton(
            "ðŸ”„ Try Again", url=f"https://t.me/{client.username}?start={message.command[1]}")])

    await _reply(message, fill(FORCE_SUB_MESSAGE, message.from_user), InlineKeyboardMarkup(rows), FORCE_PIC)


# ---------------- admin commands ----------------

@Bot.on_message(filters.command("users") & filters.private & filters.user(ADMINS))
async def users_count(client, message):
    await message.reply_text(f"<b>ðŸ‘¥ {await db.count_users()} users use this bot.</b>")


@Bot.on_message(filters.command("stats") & filters.private & filters.user(ADMINS))
async def stats(client, message):
    up = get_readable_time((datetime.now() - client.uptime).total_seconds())
    delay = int(await db.get_setting("auto_delete", FILE_AUTO_DELETE))
    await message.reply_text(
        f"<b>â± Uptime:</b> {up}\n"
        f"<b>ðŸ‘¥ Users:</b> {await db.count_users()}\n"
        f"<b>ðŸ—‘ Auto delete:</b> {get_readable_time(delay) if delay else 'off'}\n"
        f"<b>ðŸ“¢ Force sub channels:</b> {len(client.force_channels)}"
    )


@Bot.on_message(filters.command("autodelete") & filters.private & filters.user(ADMINS))
async def autodelete(client, message):
    if len(message.command) < 2:
        cur = int(await db.get_setting("auto_delete", FILE_AUTO_DELETE))
        return await message.reply_text(
            f"Current: <b>{get_readable_time(cur) if cur else 'off'}</b>\n"
            "Usage: <code>/autodelete 600</code> (seconds) or <code>/autodelete off</code>"
        )
    arg = message.command[1].lower()
    if arg in ("off", "0"):
        await db.set_setting("auto_delete", 0)
        return await message.reply_text("âœ… Auto delete turned off.")
    if not arg.isdigit():
        return await message.reply_text("âŒ Send a number of seconds or <code>off</code>.")
    await db.set_setting("auto_delete", int(arg))
    await message.reply_text(f"âœ… Auto delete set to {get_readable_time(int(arg))}.")


@Bot.on_message(filters.command("broadcast") & filters.private & filters.user(ADMINS))
async def broadcast(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast it.")
    users = await db.full_userbase()
    status = await message.reply_text("ðŸ“¡ Broadcasting...")
    ok = blocked = deleted = failed = 0
    for uid in users:
        try:
            await message.reply_to_message.copy(uid)
            ok += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await message.reply_to_message.copy(uid)
                ok += 1
            except Exception:
                failed += 1
        except UserIsBlocked:
            await db.del_user(uid)
            blocked += 1
        except InputUserDeactivated:
            await db.del_user(uid)
            deleted += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"<b>Broadcast done</b>\n\nTotal: {len(users)}\nSuccess: {ok}\n"
        f"Blocked: {blocked}\nDeleted accounts: {deleted}\nFailed: {failed}"
  )

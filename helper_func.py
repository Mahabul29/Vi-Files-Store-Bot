import asyncio
import base64
import re

from pyrogram import filters, enums
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMINS

START_BUTTONS = InlineKeyboardMarkup(
    [[InlineKeyboardButton("ðŸ˜Š About Me", callback_data="about"),
      InlineKeyboardButton("ðŸ”’ Close", callback_data="close")]]
)

_OK = {
    enums.ChatMemberStatus.OWNER,
    enums.ChatMemberStatus.ADMINISTRATOR,
    enums.ChatMemberStatus.MEMBER,
}


async def encode(string: str) -> str:
    return base64.urlsafe_b64encode(string.encode("ascii")).decode("ascii").strip("=")


async def decode(b64: str) -> str:
    b64 = b64.strip("=")
    return base64.urlsafe_b64decode((b64 + "=" * (-len(b64) % 4)).encode("ascii")).decode("ascii")


def fill(template: str, user) -> str:
    return (
        (template or "")
        .replace("{first}", user.first_name or "")
        .replace("{last}", user.last_name or "")
        .replace("{username}", ("@" + user.username) if user.username else "")
        .replace("{mention}", user.mention)
        .replace("{id}", str(user.id))
    )


def is_admin(client, uid: int) -> bool:
    if uid == client.owner_id or uid in client.cfg["mods"]:
        return True
    return (not client.is_clone) and uid in ADMINS


async def _admins(_, client, m):
    return bool(m.from_user) and is_admin(client, m.from_user.id)


admins = filters.create(_admins)


async def get_unjoined(client, user_id: int):
    """Force-sub channel ids the user has NOT joined."""
    missing = []
    for ch in client.force_channels:
        try:
            m = await client.get_chat_member(ch, user_id)
            if m.status in _OK:
                continue
            if m.status == enums.ChatMemberStatus.RESTRICTED and m.is_member:
                continue
            missing.append(ch)
        except UserNotParticipant:
            missing.append(ch)
        except Exception:
            continue
    return missing


async def _is_subscribed(_, client, update):
    if not client.force_channels:
        return True
    user_id = update.from_user.id
    if is_admin(client, user_id):
        return True
    return not await get_unjoined(client, user_id)


subscribed = filters.create(_is_subscribed)


async def get_messages(client, message_ids):
    ch = client.cfg["db_channel"]
    messages = []
    total = 0
    ids = list(message_ids)
    while total < len(ids):
        batch = ids[total:total + 200]
        try:
            msgs = await client.get_messages(ch, batch)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            msgs = await client.get_messages(ch, batch)
        except Exception:
            msgs = []
        total += len(batch)
        messages.extend(m for m in msgs if m and not m.empty)
    return messages


def forward_info(message):
    """(origin, chat, message_id) of a forwarded message (works on pyrogram & pyrofork)."""
    origin = getattr(message, "forward_origin", None)
    chat = getattr(message, "forward_from_chat", None)
    mid = getattr(message, "forward_from_message_id", None)
    if origin is not None:
        chat = getattr(origin, "chat", None) or chat
        mid = getattr(origin, "message_id", None) or mid
    return origin, chat, mid


async def get_message_id(client, message) -> int:
    ch = client.cfg["db_channel"]
    origin, fchat, fmid = forward_info(message)
    if fchat:
        return fmid if fchat.id == ch else 0
    if origin is not None or getattr(message, "forward_sender_name", None):
        return 0
    if message.text:
        m = re.match(r"https://t\.me/(?:c/)?([^/]+)/(\d+)", message.text.strip())
        if not m:
            return 0
        chan, msg_id = m.group(1), int(m.group(2))
        if chan.isdigit():
            return msg_id if f"-100{chan}" == str(ch) else 0
        uname = getattr(client.db_channel, "username", None)
        return msg_id if uname and chan.lower() == uname.lower() else 0
    return 0


def get_readable_time(seconds) -> str:
    seconds = int(seconds)
    d, r = divmod(seconds, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = [f"{v}{u}" for v, u in ((d, "d"), (h, "h"), (m, "m"), (s, "s")) if v]
    return " ".join(parts) or "0s"

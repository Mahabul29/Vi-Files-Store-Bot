import asyncio
import base64
import re

from pyrogram import filters, enums
from pyrogram.errors import FloodWait, UserNotParticipant

from config import ADMINS, CHANNEL_ID

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


async def get_unjoined(client, user_id: int):
    """Return list of force-sub channel ids the user has NOT joined."""
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
    if user_id in ADMINS:
        return True
    return not await get_unjoined(client, user_id)


subscribed = filters.create(_is_subscribed)


async def get_messages(client, message_ids):
    messages = []
    total = 0
    ids = list(message_ids)
    while total < len(ids):
        batch = ids[total:total + 200]
        try:
            msgs = await client.get_messages(CHANNEL_ID, batch)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            msgs = await client.get_messages(CHANNEL_ID, batch)
        except Exception:
            msgs = []
        total += len(batch)
        messages.extend(m for m in msgs if m and not m.empty)
    return messages


async def get_message_id(client, message) -> int:
    origin = getattr(message, "forward_origin", None)
    fchat = getattr(message, "forward_from_chat", None)
    fmid = getattr(message, "forward_from_message_id", None)
    if origin is not None:
        fchat = getattr(origin, "chat", None) or fchat
        fmid = getattr(origin, "message_id", None) or fmid
    if fchat:
        return fmid if fchat.id == CHANNEL_ID else 0
    if origin is not None or getattr(message, "forward_sender_name", None):
        return 0
    if message.text:
        m = re.match(r"https://t\.me/(?:c/)?([^/]+)/(\d+)", message.text.strip())
        if not m:
            return 0
        chan, msg_id = m.group(1), int(m.group(2))
        if chan.isdigit():
            return msg_id if f"-100{chan}" == str(CHANNEL_ID) else 0
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

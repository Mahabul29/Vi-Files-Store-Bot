import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
LOGGER = logging.getLogger("FilesStoreBot")


def _int(key, default=0):
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return default


API_HASH = os.environ.get("API_HASH", "")
APP_ID = _int("APP_ID")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = _int("OWNER_ID")
CHANNEL_ID = _int("CHANNEL_ID")
DB_URL = os.environ.get("DB_URL", "")
DB_NAME = os.environ.get("DB_NAME", "FilesStoreBot")
PORT = _int("PORT", 8080)
TG_BOT_WORKERS = _int("TG_BOT_WORKERS", 4)

FILE_AUTO_DELETE = _int("FILE_AUTO_DELETE", 0)  # seconds, 0 = off

# Force sub: up to 4 channels (0 / empty = disabled)
FORCE_SUB_CHANNELS = [
    c
    for c in (
        _int("FORCE_SUB_CHANNEL"),
        _int("FORCE_SUB_CHANNEL_2"),
        _int("FORCE_SUB_CHANNEL_3"),
        _int("FORCE_SUB_CHANNEL_4"),
    )
    if c
]

try:
    ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split()]
except ValueError:
    raise Exception("ADMINS list contains a non-integer value.")
if OWNER_ID and OWNER_ID not in ADMINS:
    ADMINS.append(OWNER_ID)

PROTECT_CONTENT = os.environ.get("PROTECT_CONTENT", "False").lower() == "true"
START_PIC = os.environ.get("START_PIC", "")
FORCE_PIC = os.environ.get("FORCE_PIC", "")

START_MESSAGE = os.environ.get(
    "START_MESSAGE",
    "<i>𝙷𝚎𝚕𝚕𝚘 {mention} \u2728\n\n𝙸 𝚊𝚖 𝚊 𝚙𝚎𝚛𝚖𝚊𝚗𝚎𝚗𝚝 𝚏𝚒𝚕𝚎 𝚜𝚝𝚘𝚛𝚎 𝚋𝚘𝚝 𝚊𝚗𝚍 𝚞𝚜𝚎𝚛𝚜 𝚌𝚊𝚗 𝚊𝚌𝚌𝚎𝚜𝚜 "
    "𝚜𝚝𝚘𝚛𝚎𝚍 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜 𝚋𝚢 𝚞𝚜𝚒𝚗𝚐 𝚊 𝚜𝚑𝚊𝚛𝚎𝚊𝚋𝚕𝚎 𝚕𝚒𝚗𝚔 𝚐𝚒𝚟𝚎𝚗 𝚋𝚢 𝚖𝚎\n\n"
    "𝚃𝚘 𝚔𝚗𝚘𝚠 𝚖𝚘𝚛𝚎 𝚌𝚕𝚒𝚌𝚔 𝚑𝚎𝚕𝚙 𝚋𝚞𝚝𝚝𝚘𝚗</i>",
)
FORCE_SUB_MESSAGE = os.environ.get(
    "FORCE_SUB_MESSAGE",
    "<b>Hello {first}!\n\nYou must join my channel(s) to use me. "
    "Join below, then tap <u>Try Again</u>.</b>",
)
USER_REPLY_TEXT = os.environ.get(
    "USER_REPLY_TEXT", "\u274c Don't send me messages directly, I'm only a file store bot."
)

# True = only ADMINS can create clones with /clone
CLONE_ADMIN_ONLY = os.environ.get("CLONE_ADMIN_ONLY", "False").lower() == "true"

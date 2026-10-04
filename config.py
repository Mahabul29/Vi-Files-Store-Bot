import logging
import os

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
    "<i>Hello {mention} \u2728\n\nI am a permanent file store bot and users can access "
    "stored messages by using a shareable link given by me\n\n"
    "To know more click help button</i>",
)
FORCE_SUB_MESSAGE = os.environ.get(
    "FORCE_SUB_MESSAGE",
    "<b>Hello {first}!\n\nYou must join my channel(s) to use me. "
    "Join below, then tap <u>Try Again</u>.</b>",
)
USER_REPLY_TEXT = os.environ.get(
    "USER_REPLY_TEXT",
    "\u274c Don't send me messages directly, I'm only a file store bot.",
)

# True = only ADMINS can create clones with /clone
CLONE_ADMIN_ONLY = os.environ.get("CLONE_ADMIN_ONLY", "False").lower() == "true"

import asyncio
from datetime import datetime

from aiohttp import web
from pyrogram import Client, enums
from pyrogram.types import ChatPrivileges

from config import (
    API_HASH, APP_ID, BOT_TOKEN, CHANNEL_ID, FILE_AUTO_DELETE, FORCE_PIC,
    FORCE_SUB_CHANNELS, FORCE_SUB_MESSAGE, LOGGER, OWNER_ID, PORT, PROTECT_CONTENT,
    START_MESSAGE, START_PIC, TG_BOT_WORKERS,
)
from database.database import db

CLONES = {}  # bot_id -> Bot instance
MAIN = {}  # {'bot': main Bot instance}
OLD_START = ("<b>𝙷𝚎𝚕𝚕𝚘 {first}!\n\n𝙸 𝚜𝚝𝚘𝚛𝚎 𝚙𝚘𝚜𝚝𝚜 𝚊𝚗𝚍 𝚏𝚒𝚕𝚎𝚜 𝚒𝚗 𝚊 𝚙𝚛𝚒𝚟𝚊𝚝𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚊𝚗𝚍 "
             "𝚜𝚑𝚊𝚛𝚎 𝚝𝚑𝚎𝚖 𝚝𝚑𝚛𝚘𝚞𝚐𝚑 𝚜𝚙𝚎𝚌𝚒𝚊𝚕 𝚕𝚒𝚗𝚔𝚜.</b>")
MAIN_SAVED = ("auto_delete",)  # settings the main bot persists in DB


def default_cfg(is_clone: bool) -> dict:
    return {
        "start_msg": START_MESSAGE,
        "start_pic": "" if is_clone else START_PIC,
        "force_msg": FORCE_SUB_MESSAGE,
        "force_pic": "" if is_clone else FORCE_PIC,
        "force": [] if is_clone else list(FORCE_SUB_CHANNELS),
        "mods": [],
        "auto_delete": 0 if is_clone else FILE_AUTO_DELETE,
        "no_forward": False if is_clone else PROTECT_CONTENT,
        "token_on": False,
        "short_site": "",
        "short_api": "",
        "token_hours": 24,
        "db_channel": CHANNEL_ID,  # clones share the main DB channel by default
        "mode": "public",  # public / private
        "active": True,
    }


class Bot(Client):
    def __init__(self, name="Bot", token=BOT_TOKEN, is_clone=False, owner_id=OWNER_ID, bot_id="main"):
        exclude = ["clone", "channel_post", "settings"] if is_clone else []
        super().__init__(
            name=name,
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins=dict(root="plugins", exclude=exclude),
            workers=TG_BOT_WORKERS,
            bot_token=token,
            in_memory=True,
        )
        self.is_clone = is_clone
        self.owner_id = owner_id
        self.bot_id = bot_id
        self.cfg = default_cfg(is_clone)
        self.invitelinks = {}
        self.fsub_titles = {}
        self.force_channels = []
        self.username = None
        self.display_name = ""
        self.db_channel = None
        self.runner = None
        self.uptime = datetime.now()

    async def save_cfg(self):
        keys = MAIN_SAVED if not self.is_clone else tuple(self.cfg.keys())
        await db.set_settings(self.bot_id, {k: self.cfg[k] for k in keys})

    async def setup_force(self):
        links, titles, chans = {}, {}, []
        for ch in self.cfg["force"]:
            try:
                chat = await self.get_chat(ch)
                link = chat.invite_link
                if not link:
                    link = await self.export_chat_invite_link(ch)
                links[ch] = link
                titles[ch] = chat.title or str(ch)
                chans.append(ch)
            except Exception as e:
                LOGGER.warning(f"[{self.username}] 𝙵𝚘𝚛𝚌𝚎 𝚜𝚞𝚋 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 {ch} 𝚜𝚔𝚒𝚙𝚙𝚎𝚍: {e}. "
                               "𝙼𝚊𝚔𝚎 𝚝𝚑𝚎 𝚋𝚘𝚝 𝚊𝚍𝚖𝚒𝚗 𝚠𝚒𝚝𝚑 𝚒𝚗𝚟𝚒𝚝𝚎-𝚕𝚒𝚗𝚔 𝚙𝚎𝚛𝚖𝚒𝚜𝚜𝚒𝚘𝚗.")
        self.invitelinks, self.fsub_titles, self.force_channels = links, titles, chans

    async def setup_db_channel(self) -> bool:
        ch = self.cfg["db_channel"]
        if not ch:
            self.db_channel = None
            return False
        try:
            chat = await self.get_chat(ch)
            test = await self.send_message(chat.id, "𝚃𝚎𝚜𝚝 𝙼𝚎𝚜𝚜𝚊𝚐𝚎")
            await test.delete()
            self.db_channel = chat
            return True
        except Exception as e:
            LOGGER.error(f"[{self.username}] 𝙲𝚊𝚗𝚗𝚘𝚝 𝚊𝚌𝚌𝚎𝚜𝚜 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 {ch}: {e}")
            self.db_channel = None
            return False

    async def start(self):
        saved = await db.get_settings(self.bot_id)
        if self.is_clone:
            self.cfg.update(saved)
            self.cfg["db_channel"] = CHANNEL_ID  # clones always use the main DB channel
            if self.cfg["start_msg"] == OLD_START:
                self.cfg["start_msg"] = START_MESSAGE
        else:
            self.cfg.update({k: v for k, v in saved.items() if k in MAIN_SAVED})

        await super().start()
        me = await self.get_me()
        self.username = me.username
        self.display_name = me.first_name or me.username
        self.uptime = datetime.now()
        self.set_parse_mode(enums.ParseMode.HTML)

        await self.setup_force()

        if not self.is_clone:
            MAIN['bot'] = self
        # clones store files through the main bot, so only the main bot needs the channel
        if not self.is_clone and not await self.setup_db_channel():
            await super().stop()
            raise RuntimeError("𝙱𝚘𝚝 𝚖𝚞𝚜𝚝 𝚋𝚎 𝚊𝚍𝚖𝚒𝚗 𝚒𝚗 𝚝𝚑𝚎 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 (𝚌𝚑𝚎𝚌𝚔 𝙲𝙷𝙰𝙽𝙽𝙴𝙻_𝙸𝙳).")

        if not self.is_clone:
            from plugins.web_server import web_server
            self.runner = web.AppRunner(await web_server())
            await self.runner.setup()
            await web.TCPSite(self.runner, "0.0.0.0", PORT).start()

        LOGGER.info(f"𝙱𝚘𝚝 𝚛𝚞𝚗𝚗𝚒𝚗𝚐 𝚊𝚜 @{self.username}")

    async def stop(self, *args):
        if self.runner:
            await self.runner.cleanup()
        await super().stop()
        LOGGER.info(f"𝙱𝚘𝚝 @{self.username} 𝚜𝚝𝚘𝚙𝚙𝚎𝚍.")


async def start_clone(token: str, owner_id: int) -> "Bot":
    if token == BOT_TOKEN:
        raise RuntimeError("𝚈𝚘𝚞 𝚌𝚊𝚗'𝚝 𝚌𝚕𝚘𝚗𝚎 𝚝𝚑𝚎 𝚖𝚊𝚒𝚗 𝚋𝚘𝚝 𝚝𝚘𝚔𝚎𝚗.")
    bot_id = token.split(":")[0]
    if bot_id in CLONES:
        raise RuntimeError("𝚃𝚑𝚒𝚜 𝚋𝚘𝚝 𝚒𝚜 𝚊𝚕𝚛𝚎𝚊𝚍𝚢 𝚌𝚕𝚘𝚗𝚎𝚍.")
    clone = Bot(name=f"clone_{bot_id}", token=token, is_clone=True, owner_id=owner_id, bot_id=bot_id)
    await clone.start()
    CLONES[bot_id] = clone
    return clone


async def stop_clone(bot_id: str):
    c = CLONES.pop(bot_id, None)
    if c:
        try:
            await c.stop()
        except Exception as e:
            LOGGER.warning(f"𝚂𝚝𝚘𝚙𝚙𝚒𝚗𝚐 𝚌𝚕𝚘𝚗𝚎 {bot_id} 𝚏𝚊𝚒𝚕𝚎𝚍: {e}")


async def ensure_db_access(main, clone) -> bool:
    """Clones store files through the main bot and need no channel access."""
    return True
    if clone.db_channel:
        return True
    try:
        await main.promote_chat_member(
            CHANNEL_ID, int(clone.bot_id),
            privileges=ChatPrivileges(
                can_post_messages=True, can_edit_messages=True, can_delete_messages=True),
        )
    except Exception as e:
        LOGGER.warning(f"𝙰𝚞𝚝𝚘-𝚙𝚛𝚘𝚖𝚘𝚝𝚎 𝚘𝚏 @{clone.username} 𝚒𝚗 𝙳𝙱 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚏𝚊𝚒𝚕𝚎𝚍: {e}")
    return await clone.setup_db_channel()


async def restart_clone(bot_id: str, main=None):
    c = CLONES.get(bot_id)
    if not c:
        return None
    token, owner = c.bot_token, c.owner_id
    await stop_clone(bot_id)
    await asyncio.sleep(1)
    try:
        new = await start_clone(token, owner)
    except Exception as e:
        LOGGER.error(f"𝚁𝚎𝚜𝚝𝚊𝚛𝚝𝚒𝚗𝚐 𝚌𝚕𝚘𝚗𝚎 {bot_id} 𝚏𝚊𝚒𝚕𝚎𝚍: {e}")
        return None
    if main is not None:
        await ensure_db_access(main, new)
    return new

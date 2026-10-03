import asyncio
from datetime import datetime

from aiohttp import web
from pyrogram import Client, enums

from config import (
    API_HASH, APP_ID, BOT_TOKEN, CHANNEL_ID, FILE_AUTO_DELETE, FORCE_PIC,
    FORCE_SUB_CHANNELS, FORCE_SUB_MESSAGE, LOGGER, OWNER_ID, PORT, PROTECT_CONTENT,
    START_MESSAGE, START_PIC, TG_BOT_WORKERS,
)
from database.database import db

CLONES = {}  # bot_id -> Bot instance
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
        exclude = ["clone", "channel_post"] if is_clone else []
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
                LOGGER.warning(f"[{self.username}] Force sub channel {ch} skipped: {e}. "
                               "Make the bot admin with invite-link permission.")
        self.invitelinks, self.fsub_titles, self.force_channels = links, titles, chans

    async def setup_db_channel(self) -> bool:
        ch = self.cfg["db_channel"]
        if not ch:
            self.db_channel = None
            return False
        try:
            chat = await self.get_chat(ch)
            test = await self.send_message(chat.id, "Test Message")
            await test.delete()
            self.db_channel = chat
            return True
        except Exception as e:
            LOGGER.error(f"[{self.username}] Cannot access DB channel {ch}: {e}")
            self.db_channel = None
            return False

    async def start(self):
        saved = await db.get_settings(self.bot_id)
        if self.is_clone:
            self.cfg.update(saved)
            if not self.cfg.get("db_channel"):
                self.cfg["db_channel"] = CHANNEL_ID
        else:
            self.cfg.update({k: v for k, v in saved.items() if k in MAIN_SAVED})

        await super().start()
        me = await self.get_me()
        self.username = me.username
        self.display_name = me.first_name or me.username
        self.uptime = datetime.now()
        self.set_parse_mode(enums.ParseMode.HTML)

        await self.setup_force()

        if not await self.setup_db_channel() and not self.is_clone:
            await super().stop()
            raise RuntimeError("Bot must be admin in the DB channel (check CHANNEL_ID).")

        if not self.is_clone:
            from plugins.web_server import web_server
            self.runner = web.AppRunner(await web_server())
            await self.runner.setup()
            await web.TCPSite(self.runner, "0.0.0.0", PORT).start()

        LOGGER.info(f"Bot running as @{self.username}")

    async def stop(self, *args):
        if self.runner:
            await self.runner.cleanup()
        await super().stop()
        LOGGER.info(f"Bot @{self.username} stopped.")


async def start_clone(token: str, owner_id: int) -> "Bot":
    if token == BOT_TOKEN:
        raise RuntimeError("You can't clone the main bot token.")
    bot_id = token.split(":")[0]
    if bot_id in CLONES:
        raise RuntimeError("This bot is already cloned.")
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
            LOGGER.warning(f"Stopping clone {bot_id} failed: {e}")


async def restart_clone(bot_id: str):
    c = CLONES.get(bot_id)
    if not c:
        return
    token, owner = c.bot_token, c.owner_id
    await stop_clone(bot_id)
    await asyncio.sleep(1)
    try:
        new = await start_clone(token, owner)
        await new.send_message(owner, "✅ Clone restarted.")
    except Exception as e:
        LOGGER.error(f"Restarting clone {bot_id} failed: {e}")
        

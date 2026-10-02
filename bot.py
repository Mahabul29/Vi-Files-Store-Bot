from datetime import datetime

from aiohttp import web
from pyrogram import Client, enums

from config import (
    API_HASH, APP_ID, BOT_TOKEN, CHANNEL_ID, FORCE_SUB_CHANNELS,
    LOGGER, PORT, TG_BOT_WORKERS,
)

CLONES = {}  # bot_id -> Bot instance


class Bot(Client):
    def __init__(self, name="Bot", token=BOT_TOKEN, is_clone=False):
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
        self.invitelinks = {}
        self.force_channels = []
        self.username = None
        self.db_channel = None
        self.runner = None

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username = me.username
        self.uptime = datetime.now()
        self.set_parse_mode(enums.ParseMode.HTML)

        # Force sub channels (up to 4)
        for ch in FORCE_SUB_CHANNELS:
            try:
                chat = await self.get_chat(ch)
                link = chat.invite_link
                if not link:
                    await self.export_chat_invite_link(ch)
                    chat = await self.get_chat(ch)
                    link = chat.invite_link
                self.invitelinks[ch] = link
                self.force_channels.append(ch)
            except Exception as e:
                LOGGER.warning(f"[{self.username}] Force sub channel {ch} skipped: {e}. "
                               "Make the bot admin with invite-link permission.")

        # DB channel check
        try:
            self.db_channel = await self.get_chat(CHANNEL_ID)
            test = await self.send_message(self.db_channel.id, "Test Message")
            await test.delete()
        except Exception as e:
            LOGGER.error(f"[{self.username}] Cannot access CHANNEL_ID {CHANNEL_ID}: {e}")
            await super().stop()
            raise RuntimeError("Bot must be admin in the DB channel.")

        # Web server (main bot only)
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
        LOGGER.info("Bot stopped.")


async def start_clone(token: str) -> "Bot":
    bot_id = token.split(":")[0]
    if bot_id in CLONES:
        raise RuntimeError("This clone is already running.")
    clone = Bot(name=f"clone_{bot_id}", token=token, is_clone=True)
    await clone.start()
    CLONES[bot_id] = clone
    return clone

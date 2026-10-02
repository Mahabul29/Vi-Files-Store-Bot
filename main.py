import asyncio

from pyrogram import idle

from bot import Bot, CLONES, start_clone
from config import LOGGER
from database.database import db


async def main():
    app = Bot()
    await app.start()

    for doc in await db.get_clones():
        try:
            await start_clone(doc["token"])
        except Exception as e:
            LOGGER.warning(f"Clone {doc['_id']} failed to start: {e}")

    await idle()

    for c in list(CLONES.values()):
        await c.stop()
    await app.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

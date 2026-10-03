import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import idle  # noqa: E402

from bot import Bot, CLONES, start_clone  # noqa: E402
from config import LOGGER, OWNER_ID  # noqa: E402
from database.database import db  # noqa: E402


async def main():
    app = Bot()
    await app.start()

    for doc in await db.get_clones():
        try:
            await start_clone(doc["token"], doc.get("owner", OWNER_ID))
        except Exception as e:
            LOGGER.warning(f"Clone {doc['_id']} failed to start: {e}")

    await idle()

    for c in list(CLONES.values()):
        await c.stop()
    await app.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

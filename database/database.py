import time

import motor.motor_asyncio
from config import DB_URL, DB_NAME


class Database:
    def __init__(self, uri, name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[name]
        self.users = self.db["bot_users"]
        self.bots = self.db["bot_settings"]
        self.clones = self.db["clones"]
        self.tokens = self.db["access_tokens"]
        self.verified = self.db["verified_users"]
        self.files = self.db["clone_files"]

    # ---- users (scoped per bot) ----
    async def add_user(self, bot: str, uid: int):
        await self.users.update_one(
            {"_id": f"{bot}:{uid}"}, {"$set": {"bot": bot, "uid": uid}}, upsert=True
        )

    async def full_userbase(self, bot: str):
        return [d["uid"] async for d in self.users.find({"bot": bot})]

    async def count_users(self, bot: str) -> int:
        return await self.users.count_documents({"bot": bot})

    async def del_user(self, bot: str, uid: int):
        await self.users.delete_one({"_id": f"{bot}:{uid}"})

    async def del_bot_users(self, bot: str):
        await self.users.delete_many({"bot": bot})

    # ---- bot settings ----
    async def get_settings(self, bot: str) -> dict:
        doc = await self.bots.find_one({"_id": bot})
        return doc.get("data", {}) if doc else {}

    async def set_settings(self, bot: str, data: dict):
        await self.bots.update_one({"_id": bot}, {"$set": {"data": data}}, upsert=True)

    async def del_settings(self, bot: str):
        await self.bots.delete_one({"_id": bot})

    # ---- clones ----
    async def add_clone(self, bot_id: str, token: str, owner: int):
        await self.clones.update_one(
            {"_id": bot_id}, {"$set": {"token": token, "owner": owner}}, upsert=True
        )

    async def get_clones(self):
        return await self.clones.find().to_list(length=None)

    async def del_clone(self, bot_id: str):
        await self.clones.delete_one({"_id": bot_id})

    # ---- files stored through clones (shared main DB channel) ----
    async def add_file(self, bot: str, msg_id: int):
        await self.files.update_one(
            {"_id": f"{bot}:{msg_id}"}, {"$set": {"bot": bot, "msg": msg_id}}, upsert=True
        )

    async def owned_ids(self, bot: str, ids):
        ids = list(ids)
        found = {d["msg"] async for d in self.files.find({"bot": bot, "msg": {"$in": ids}})}
        return [i for i in ids if i in found]

    async def del_bot_files(self, bot: str):
        await self.files.delete_many({"bot": bot})

    # ---- access token verification ----
    async def create_token(self, bot: str, uid: int, token: str, payload: str):
        await self.tokens.insert_one(
            {"_id": token, "bot": bot, "uid": uid, "payload": payload, "created": time.time()}
        )

    async def pop_token(self, bot: str, uid: int, token: str):
        return await self.tokens.find_one_and_delete({"_id": token, "bot": bot, "uid": uid})

    async def set_verified(self, bot: str, uid: int, until: float):
        await self.verified.update_one(
            {"_id": f"{bot}:{uid}"}, {"$set": {"until": until}}, upsert=True
        )

    async def is_verified(self, bot: str, uid: int) -> bool:
        doc = await self.verified.find_one({"_id": f"{bot}:{uid}"})
        return bool(doc and doc.get("until", 0) > time.time())


db = Database(DB_URL, DB_NAME)

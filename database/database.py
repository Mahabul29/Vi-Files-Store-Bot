import motor.motor_asyncio
from config import DB_URL, DB_NAME


class Database:
    def __init__(self, uri, name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[name]
        self.users = self.db["users"]
        self.settings = self.db["settings"]
        self.clones = self.db["clones"]

    # ---- users ----
    async def present_user(self, user_id: int) -> bool:
        return bool(await self.users.find_one({"_id": user_id}))

    async def add_user(self, user_id: int):
        await self.users.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)

    async def full_userbase(self):
        return [d["_id"] async for d in self.users.find()]

    async def count_users(self) -> int:
        return await self.users.count_documents({})

    async def del_user(self, user_id: int):
        await self.users.delete_one({"_id": user_id})

    # ---- settings ----
    async def get_setting(self, key, default=None):
        doc = await self.settings.find_one({"_id": key})
        return doc["value"] if doc else default

    async def set_setting(self, key, value):
        await self.settings.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)

    # ---- clones ----
    async def add_clone(self, bot_id: str, token: str, owner: int):
        await self.clones.update_one(
            {"_id": bot_id}, {"$set": {"token": token, "owner": owner}}, upsert=True
        )

    async def get_clones(self):
        return await self.clones.find().to_list(length=None)

    async def del_clone(self, bot_id: str):
        await self.clones.delete_one({"_id": bot_id})


db = Database(DB_URL, DB_NAME)

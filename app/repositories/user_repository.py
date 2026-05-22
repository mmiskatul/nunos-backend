import asyncio

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import oid, utcnow


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.users
        self._is_async = isinstance(db, AsyncIOMotorDatabase)

    @staticmethod
    def _build_query(search: str | None = None, status: str | None = None) -> dict:
        query: dict = {}
        and_filters: list[dict] = []

        if search:
            and_filters.append(
                {
                    "$or": [
                        {"full_name": {"$regex": search, "$options": "i"}},
                        {"email": {"$regex": search, "$options": "i"}},
                        {"phone": {"$regex": search, "$options": "i"}},
                    ]
                }
            )

        if status:
            normalized_status = status.lower()
            if normalized_status == "active":
                and_filters.append(
                    {
                        "$or": [
                            {"status": "active"},
                            {"status": {"$exists": False}, "is_active": {"$ne": False}},
                        ]
                    }
                )
            elif normalized_status == "blocked":
                and_filters.append(
                    {
                        "$or": [
                            {"status": "blocked"},
                            {"is_active": False},
                        ]
                    }
                )
            else:
                and_filters.append({"status": normalized_status})

        if len(and_filters) == 1:
            query.update(and_filters[0])
        elif and_filters:
            query["$and"] = and_filters

        return query

    async def create_user(self, payload: dict) -> dict:
        now = utcnow()
        payload.update({"created_at": now, "updated_at": now})
        if self._is_async:
            result = await self.collection.insert_one(payload)
        else:
            result = await asyncio.to_thread(self.collection.insert_one, payload)
        return await self.find_by_id(str(result.inserted_id))

    async def find_by_id(self, user_id: str) -> dict | None:
        query = {"_id": oid(user_id)}
        if self._is_async:
            return await self.collection.find_one(query)
        return await asyncio.to_thread(self.collection.find_one, query)

    async def find_by_email(self, email: str) -> dict | None:
        query = {"email": email}
        if self._is_async:
            return await self.collection.find_one(query)
        return await asyncio.to_thread(self.collection.find_one, query)

    async def find_by_phone(self, phone: str) -> dict | None:
        query = {"phone": phone}
        if self._is_async:
            return await self.collection.find_one(query)
        return await asyncio.to_thread(self.collection.find_one, query)

    async def find_by_email_or_phone(self, identifier: str) -> dict | None:
        query = {"$or": [{"email": identifier}, {"phone": identifier}]}
        if self._is_async:
            return await self.collection.find_one(query)
        return await asyncio.to_thread(self.collection.find_one, query)

    async def get_by_id(self, user_id: str) -> dict | None:
        return await self.find_by_id(user_id)

    async def list_users(
        self,
        *,
        limit: int = 50,
        skip: int = 0,
        search: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        query = self._build_query(search=search, status=status)

        if self._is_async:
            cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        return await asyncio.to_thread(self._list_users_sync, query, skip, limit)

    async def count_users(self, *, search: str | None = None, status: str | None = None) -> int:
        query = self._build_query(search=search, status=status)

        if self._is_async:
            return await self.collection.count_documents(query)
        return await asyncio.to_thread(self.collection.count_documents, query)

    async def update_profile(self, user_id: str, payload: dict) -> dict | None:
        query = {"_id": oid(user_id)}
        update = {"$set": {**payload, "updated_at": utcnow()}}
        if self._is_async:
            await self.collection.update_one(query, update)
        else:
            await asyncio.to_thread(self.collection.update_one, query, update)
        return await self.find_by_id(user_id)

    async def update_status(self, user_id: str, status: str) -> dict | None:
        query = {"_id": oid(user_id)}
        normalized_status = status.lower()
        update = {
            "$set": {
                "status": normalized_status,
                "is_active": normalized_status == "active",
                "updated_at": utcnow(),
            }
        }
        if self._is_async:
            await self.collection.update_one(query, update)
        else:
            await asyncio.to_thread(self.collection.update_one, query, update)
        return await self.find_by_id(user_id)

    async def update_password_by_email(self, email: str, password_hash: str) -> bool:
        query = {"email": email}
        update = {"$set": {"password_hash": password_hash, "updated_at": utcnow()}}
        if self._is_async:
            result = await self.collection.update_one(query, update)
        else:
            result = await asyncio.to_thread(self.collection.update_one, query, update)
        return result.modified_count == 1

    async def add_points(self, user_id: str, points: int) -> None:
        query = {"_id": oid(user_id)}
        update = {"$inc": {"points_balance": points}, "$set": {"updated_at": utcnow()}}
        if self._is_async:
            await self.collection.update_one(query, update)
        else:
            await asyncio.to_thread(self.collection.update_one, query, update)

    def _list_users_sync(self, query: dict, skip: int, limit: int) -> list[dict]:
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        return list(cursor)

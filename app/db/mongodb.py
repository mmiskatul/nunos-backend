from threading import Lock

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import Settings


class MongoDatabase:
    def __init__(self, uri: str, db_name: str):
        self._client = MongoClient(uri)
        self._db = self._client[db_name]

    @property
    def db(self) -> Database:
        return self._db

    def close(self) -> None:
        self._client.close()


class MongoDatabaseSingleton:
    _instance: MongoDatabase | None = None
    _lock = Lock()

    @classmethod
    def get_instance(cls, settings: Settings) -> MongoDatabase:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = MongoDatabase(settings.mongodb_uri, settings.mongodb_db_name)
        return cls._instance


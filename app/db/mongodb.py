from threading import Lock

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import Settings


class MongoDatabase:
    def __init__(
        self,
        uri: str,
        db_name: str,
        *,
        connect_timeout_ms: int = 5_000,
        server_selection_timeout_ms: int = 8_000,
        socket_timeout_ms: int = 10_000,
    ):
        self._client = MongoClient(
            uri,
            connectTimeoutMS=connect_timeout_ms,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
            socketTimeoutMS=socket_timeout_ms,
            maxIdleTimeMS=60_000,
        )
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
                    cls._instance = MongoDatabase(
                        settings.mongodb_uri,
                        settings.mongodb_db_name,
                        connect_timeout_ms=settings.mongodb_connect_timeout_ms,
                        server_selection_timeout_ms=settings.mongodb_server_selection_timeout_ms,
                        socket_timeout_ms=settings.mongodb_socket_timeout_ms,
                    )
        return cls._instance


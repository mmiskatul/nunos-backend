from fastapi import Depends, Request

from app.db.mongodb import MongoDatabase
from app.modules.vendor.repositories_vendor import VendorRepository
from app.repositories.user_repository import UserRepository


def get_db(request: Request) -> MongoDatabase:
    return request.app.state.db  # type: ignore[return-value]


def get_vendor_repository(db: MongoDatabase = Depends(get_db)) -> VendorRepository:
    return VendorRepository(db.db)


def get_user_repository(db: MongoDatabase = Depends(get_db)) -> UserRepository:
    return UserRepository(db.db)

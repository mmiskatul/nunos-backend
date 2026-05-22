from fastapi import Depends
from pymongo.database import Database

from app.core.config import Settings, get_settings
from app.db.mongodb import MongoDatabaseSingleton
from app.modules.vendor.repositories_vendor import VendorRepository
from app.repositories.user_repository import UserRepository


def get_platform_admin_db(settings: Settings = Depends(get_settings)) -> Database:
    return MongoDatabaseSingleton.get_instance(settings).db


def get_vendor_repository(db: Database = Depends(get_platform_admin_db)) -> VendorRepository:
    return VendorRepository(db)


def get_user_repository(db: Database = Depends(get_platform_admin_db)) -> UserRepository:
    return UserRepository(db)

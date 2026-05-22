from fastapi import Depends

from app.core.config import Settings, get_settings
from app.db.mongodb import MongoDatabase
from app.db.mongodb import MongoDatabaseSingleton
from app.modules.customer.repositories_customer import CustomerRepository
from app.modules.customer.service_customer import CustomerService


def get_db(settings: Settings = Depends(get_settings)) -> MongoDatabase:
    return MongoDatabaseSingleton.get_instance(settings)


def get_customer_repository(db: MongoDatabase = Depends(get_db)) -> CustomerRepository:
    return CustomerRepository(db.db)


def get_customer_service(repo: CustomerRepository = Depends(get_customer_repository)) -> CustomerService:
    return CustomerService(repo)


from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Nunos Backend"
    api_v1_prefix: str = "/api/v1"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "nunos"

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    password_reset_token_expire_minutes: int = 30
    password_reset_code_expire_minutes: int = 10
    password_reset_code_length: int = 6
    debug_return_reset_code: bool = True

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Nunos"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

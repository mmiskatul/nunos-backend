from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Nuno Backend"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "nuno"

    jwt_secret_key: str = Field("change-me-please", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10
    refresh_token_expire_minutes: int = 60 * 24 * 30
    reset_token_expire_minutes: int = 15

    otp_expire_minutes: int = 10
    otp_length: int = 6
    signup_pending_expire_minutes: int = 30
    signup_verification_code_length: int = 6
    signup_verification_code_expire_minutes: int = 10
    signup_verification_token_expire_minutes: int = 30
    debug_return_signup_code: bool = False
    password_reset_code_length: int = 6
    password_reset_code_expire_minutes: int = 10
    password_reset_token_expire_minutes: int = 15
    debug_return_reset_code: bool = False

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "Nuno"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    platform_admin_email: str | None = None
    platform_admin_password: str | None = None
    platform_admin_full_name: str = "Platform Admin"
    platform_admin_phone: str | None = None

    loyalty_points_on_confirm: int = 50

    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloudinary_folder: str = "nunu-service-provider"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: int = 20

    google_api_key: str | None = None
    google_oauth_client_ids: list[str] = Field(default_factory=list)


@lru_cache
def get_settings() -> Settings:
    return Settings()

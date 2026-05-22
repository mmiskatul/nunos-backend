from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class LocationPreferenceUpdate(BaseModel):
    enable_location: bool


class PersonalDetailsUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    date_of_birth: date | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        return normalized or None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def normalize_date_of_birth(cls, value: str | date | None) -> str | date | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class PersonalDetailsResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    profile_image_url: str | None = None
    created_at: datetime
    points_balance: int = 0
    location_enabled: bool = False


class ImageUploadResponse(BaseModel):
    profile_image_url: str
    message: str = "Profile image updated successfully."

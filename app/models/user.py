from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.common import MongoDocument


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "full_name": "Samira Rahman",
            "email": "samira@example.com",
            "phone": "+8801712345678",
            "password": "StrongPass123!",
            "location_enabled": True,
            "latitude": 23.8103,
            "longitude": 90.4125,
        }
    })

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    location_enabled: bool = False
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_meters: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_contact(self) -> "UserCreateRequest":
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        if self.location_enabled and (self.latitude is None or self.longitude is None):
            raise ValueError("Latitude and longitude are required when location is enabled")
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email_or_phone": "samira@example.com",
            "password": "StrongPass123!",
        }
    })

    email_or_phone: str
    password: str


class SocialLoginRequest(BaseModel):
    provider: str = Field(pattern="^(google)$")
    id_token: str = Field(min_length=20)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    session_token: str | None = None
    token_type: str = "bearer"


class RegistrationResponse(BaseModel):
    message: str
    email: EmailStr


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=10)

    @field_validator("otp")
    @classmethod
    def otp_digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("OTP must contain digits only")
        return value


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=10)

    @field_validator("otp")
    @classmethod
    def otp_digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("OTP must contain digits only")
        return value


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserDB(MongoDocument):
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    password_hash: str
    role: str = "customer"
    points_balance: int = 0
    is_active: bool = True
    location_enabled: bool = False
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy_meters: float | None = None


class UserPublic(BaseModel):
    id: str
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    role: str = "customer"
    points_balance: int
    created_at: datetime


class LoyaltyResponse(BaseModel):
    points_balance: int
    tier: str

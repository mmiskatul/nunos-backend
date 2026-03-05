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
        }
    })

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_contact(self) -> "UserCreateRequest":
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
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


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


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
    points_balance: int = 0
    is_active: bool = True


class UserPublic(BaseModel):
    id: str
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    points_balance: int
    created_at: datetime


class LoyaltyResponse(BaseModel):
    points_balance: int
    tier: str

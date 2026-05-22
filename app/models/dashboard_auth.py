from pydantic import BaseModel, Field, field_validator

from app.core.contact import parse_email_or_phone


class DashboardLoginRequest(BaseModel):
    email_or_phone: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class DashboardAdminPublic(BaseModel):
    id: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    role: str = "platform_admin"
    status: str = "active"


class DashboardAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: DashboardAdminPublic


class DashboardForgotPasswordRequest(BaseModel):
    email_or_phone: str

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class DashboardVerifyResetCodeRequest(BaseModel):
    email_or_phone: str
    code: str = Field(min_length=4, max_length=10)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Code must contain digits only.")
        return value


class DashboardResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)

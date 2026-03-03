from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.contact import parse_email_or_phone


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email_or_phone: str
    signup_token: str = Field(min_length=16)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    enable_location: bool = False

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value

    @model_validator(mode="after")
    def validate_passwords(self) -> "SignupRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm_password must match.")
        return self


class LoginRequest(BaseModel):
    email_or_phone: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class SocialLoginRequest(BaseModel):
    provider: str = Field(pattern="^(google|apple)$")
    provider_token: str = Field(min_length=10)


class ForgotPasswordRequest(BaseModel):
    email_or_phone: str

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class SignupCodeRequest(BaseModel):
    email_or_phone: str

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class VerifySignupCodeRequest(BaseModel):
    email_or_phone: str
    validation_code: str = Field(min_length=4, max_length=8)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=16)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match.")
        return self


class VerifyResetCodeRequest(BaseModel):
    email_or_phone: str
    validation_code: str = Field(min_length=4, max_length=8)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    enable_location: bool = False
    auth_provider: str = "local"


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordResponse(MessageResponse):
    validation_code: str | None = None


class VerifyResetCodeResponse(MessageResponse):
    reset_token: str | None = None


class VerifySignupCodeResponse(MessageResponse):
    signup_token: str | None = None

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.contact import parse_email_or_phone


class AdminRegisterCodeRequest(BaseModel):
    email_or_phone: str

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class AdminVerifyRegisterCodeRequest(BaseModel):
    email_or_phone: str
    validation_code: str = Field(min_length=4, max_length=8)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class AdminRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email_or_phone: str
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    signup_token: str = Field(min_length=16)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value

    @model_validator(mode="after")
    def validate_passwords(self) -> "AdminRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm_password must match.")
        return self


class AdminLoginRequest(BaseModel):
    email_or_phone: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class AdminForgotPasswordRequest(BaseModel):
    email_or_phone: str

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class AdminVerifyResetCodeRequest(BaseModel):
    email_or_phone: str
    validation_code: str = Field(min_length=4, max_length=8)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class AdminResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=16)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self) -> "AdminResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match.")
        return self


class AdminPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    status: str = "active"
    role: str = "platform_admin"


class AdminAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminPublic


class AdminMessageResponse(BaseModel):
    message: str


class AdminCodeResponse(AdminMessageResponse):
    validation_code: str | None = None


class AdminVerifyCodeResponse(AdminMessageResponse):
    signup_token: str | None = None
    reset_token: str | None = None


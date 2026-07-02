from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.contact import parse_email_or_phone


class VendorSignupCodeRequest(BaseModel):
    email_or_phone: str

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class VendorVerifySignupCodeRequest(BaseModel):
    email_or_phone: str
    validation_code: str = Field(min_length=4, max_length=8)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class VendorRegisterRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    owner_full_name: str = Field(min_length=2, max_length=80)
    email_or_phone: str
    phone: str | None = None
    address: str = Field(min_length=5, max_length=255)
    city: str = Field(min_length=2, max_length=80)
    website: str | None = None
    business_description: str = Field(min_length=10, max_length=1000)
    trade_license_number: str = Field(min_length=4, max_length=80)
    trade_license_document_url: str = Field(min_length=8, max_length=1000)
    owner_manager_id_document_url: str = Field(min_length=8, max_length=1000)
    terms_accepted: bool = False
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    signup_token: str = Field(min_length=16)
    category: str = Field(default="Restaurant", min_length=2, max_length=60)
    categories: list[str] | None = None
    event_types: list[str] | None = None
    venue_capacity: int | None = None
    ticket_pricing_type: str | None = None
    event_location_preference: str | None = None
    equipment_availability: list[str] | None = None

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parse_email_or_phone(value)
        return value

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized: list[str] = []
        for item in value:
            label = str(item or "").strip()
            if not label:
                continue
            if label not in normalized:
                normalized.append(label)
        return normalized or None

    @model_validator(mode="after")
    def validate_passwords(self) -> "VendorRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm_password must match.")
        if not self.terms_accepted:
            raise ValueError("terms_accepted must be true.")
        if self.categories:
            self.category = self.categories[0]
        else:
            self.categories = [self.category]
        return self


class VendorLoginRequest(BaseModel):
    email_or_phone: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class VendorForgotPasswordRequest(BaseModel):
    email_or_phone: str

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class VendorVerifyResetCodeRequest(BaseModel):
    email_or_phone: str
    validation_code: str = Field(min_length=4, max_length=8)

    @field_validator("email_or_phone")
    @classmethod
    def validate_email_or_phone(cls, value: str) -> str:
        parse_email_or_phone(value)
        return value


class VendorResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=16)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self) -> "VendorResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match.")
        return self


class VendorKycSubmitRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=60)
    owner_full_name: str = Field(min_length=2, max_length=80)
    email: str
    phone: str
    address: str = Field(min_length=5, max_length=255)
    website: str | None = None
    description: str | None = None
    document_urls: list[str] = Field(default_factory=list, max_length=10)


class VendorPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    business_name: str
    owner_full_name: str
    email: str | None = None
    phone: str | None = None
    status: str = "pending_approval"
    kyc_status: str = "not_submitted"


class VendorAuthResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    session_token: str | None = None
    token_type: str = "bearer"
    vendor: VendorPublic


class VendorRefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


class VendorMessageResponse(BaseModel):
    message: str


class VendorDocumentUploadResponse(BaseModel):
    message: str
    url: str


class VendorCodeRequestResponse(VendorMessageResponse):
    validation_code: str | None = None


class VendorVerifyCodeResponse(VendorMessageResponse):
    signup_token: str | None = None
    reset_token: str | None = None


class VendorKycStatusResponse(BaseModel):
    kyc_status: str
    submitted_at: str | None = None
    reviewed_at: str | None = None
    rejection_reason: str | None = None


class VendorRegistrationStatusResponse(BaseModel):
    status: str
    kyc_status: str
    rejection_reason: str | None = None

from pydantic import BaseModel, Field, model_validator


class BookingStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(confirmed|pending|canceled|cancelled|complete|check_in)$")
    note: str | None = None


class BookingRescheduleRequest(BaseModel):
    date: str
    time: str
    note: str | None = None


class AssetUploadRequest(BaseModel):
    asset_url: str = Field(min_length=8, max_length=1000)
    asset_type: str | None = Field(default=None, pattern="^(menu|gallery)$")
    file_name: str | None = None
    mime_type: str | None = None


class RoomUpsertRequest(BaseModel):
    name: str
    size_sqm: int = Field(ge=1)
    max_guests: int = Field(ge=1, le=20)
    bed_type: str
    number_of_beds: int = Field(ge=1, le=20)
    description: str = ""
    base_price: float = Field(ge=0)
    weekend_price: float = Field(ge=0)
    default_discount_percent: float = Field(ge=0, le=100)
    amenities: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    inventory_count: int = Field(default=1, ge=0)
    min_stay_nights: int = Field(default=1, ge=1)
    max_stay_nights: int = Field(default=30, ge=1)
    active_status: bool = True


class RoomAvailabilityRequest(BaseModel):
    available: bool
    maintenance_note: str | None = None


class ServiceUpsertRequest(BaseModel):
    name: str
    category: str
    price: float = Field(ge=0)
    delivery_time: str = ""
    description: str = ""
    images: list[str] = Field(default_factory=list)
    active_status: bool = True


class PromotionUpsertRequest(BaseModel):
    promotion_name: str
    internal_description: str = ""
    offer_type: str = Field(pattern="^(percentage|fixed_amount|happy_hour|custom_deal)$")
    discount_value: float = Field(ge=0)
    applicable_to: str = "All Services"
    start_date: str
    end_date: str
    recurring_days: list[str] = Field(default_factory=list)
    require_promo_code: bool = False
    promo_code: str | None = None
    first_time_customers_only: bool = False
    minimum_spend: float | None = Field(default=None, ge=0)
    active: bool = True


class PromotionStatusRequest(BaseModel):
    active: bool


class ReviewReplyRequest(BaseModel):
    reply_text: str = Field(min_length=2, max_length=2000)


class LoyaltySettingsRequest(BaseModel):
    enable_loyalty_program: bool
    points_rule_type: str = Field(pattern="^(points_per_currency|percentage_based)$")
    points_earned: float = Field(ge=0)
    currency_unit: float = Field(default=1, ge=0)
    percentage_value: float = Field(default=0, ge=0, le=100)
    first_booking_bonus: int = Field(default=0, ge=0)
    review_bonus_points: int = Field(default=0, ge=0)
    points_expiry_policy: str = "1 Year"


class VendorSettingsGeneralRequest(BaseModel):
    business_name: str
    legal_entity_name: str | None = None
    business_address: str | None = None
    logo_url: str | None = None
    cover_image_url: str | None = None
    booking_availability_slots: list[str] = Field(default_factory=list)
    buffer_time_minutes: int = Field(default=15, ge=0, le=240)
    front_desk_phone: str | None = None
    reservations_email: str | None = None
    emergency_contact: str | None = None


class VendorSettingsProfileRequest(BaseModel):
    business_name: str
    category: str
    email_address: str
    phone_number: str
    about_business: str = ""
    office_address: str | None = None
    website: str | None = None
    map_embed_url: str | None = None
    avatar_url: str | None = None


class VendorSettingsCommissionRequest(BaseModel):
    commission_percent: float = Field(ge=0, le=100)


class VendorLegalDocRequest(BaseModel):
    content: str
    audience: str = Field(pattern="^(apps|business)$")


class VendorSupportTicketCreateRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)


class VendorSupportTicketMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    metadata: dict = Field(default_factory=dict)


class NotificationSettingsRequest(BaseModel):
    booking_alerts: bool = True
    review_alerts: bool = True


class NotificationActionRequest(BaseModel):
    action: str = Field(pattern="^(accept_request|view_details|reply_review|mark_read)$")


class PlatformCampaignJoinRequest(BaseModel):
    join: bool


class VendorPasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self) -> "VendorPasswordChangeRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match.")
        return self

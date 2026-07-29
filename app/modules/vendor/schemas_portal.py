from datetime import date, datetime, time
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.vendor_categories import normalize_account_categories


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
    service_type: str = Field(default="restaurant", pattern="^(restaurant|hotel|spa)$")
    file_name: str | None = None
    mime_type: str | None = None

    @field_validator("asset_url")
    @classmethod
    def validate_asset_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("asset_url must be an absolute HTTP or HTTPS URL.")
        return value.strip()


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
    tax_included: bool = True
    amenities: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    inventory_count: int = Field(default=1, ge=0)
    min_stay_nights: int = Field(default=1, ge=1)
    max_stay_nights: int = Field(default=30, ge=1)
    active_status: bool = True

    @model_validator(mode="after")
    def validate_stay_range(self):
        if self.max_stay_nights < self.min_stay_nights:
            raise ValueError("Maximum stay must be greater than or equal to minimum stay.")
        return self


class RoomAvailabilityRequest(BaseModel):
    available: bool
    maintenance_note: str | None = None


class ServiceUpsertRequest(BaseModel):
    name: str
    service_type: str = Field(default="hotel", pattern="^(restaurant|hotel|spa)$")
    category: str
    price: float = Field(ge=0)
    delivery_time: str = ""
    description: str = ""
    images: list[str] = Field(default_factory=list)
    active_status: bool = True


class VendorEventUpsertRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    category: str = Field(min_length=2, max_length=60)
    event_type: str = Field(min_length=2, max_length=80)
    booking_mode: str = Field(default="simple", pattern="^(simple|detailed)$")
    event_date: str
    start_time: str
    end_time: str
    timezone: str = Field(default="Asia/Dhaka", min_length=2, max_length=80)
    venue: str = Field(min_length=2, max_length=500)
    latitude: float | None = None
    longitude: float | None = None
    capacity: int = Field(ge=1, le=100000)
    ticket_price: float = Field(ge=0)
    registration_deadline: str | None = None
    description: str = Field(default="", max_length=5000)
    banner_image_url: str | None = None
    active_status: bool = True
    status: str = Field(default="draft", pattern="^(draft|published|archived|cancelled)$")

    @field_validator("title", "category", "event_type", "timezone", "venue", "description", mode="before")
    @classmethod
    def _strip_text_fields(cls, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("event_date")
    @classmethod
    def _validate_event_date(cls, value: str) -> str:
        normalized = value.strip()
        date.fromisoformat(normalized)
        return normalized

    @field_validator("start_time", "end_time")
    @classmethod
    def _validate_time_fields(cls, value: str) -> str:
        normalized = value.strip()
        time.fromisoformat(normalized)
        return normalized

    @field_validator("registration_deadline", mode="before")
    @classmethod
    def _normalize_registration_deadline(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            return normalized
        return value

    @field_validator("banner_image_url", mode="before")
    @classmethod
    def _normalize_banner_image_url(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "canceled":
                return "cancelled"
            return normalized
        return value

    @field_validator("booking_mode", mode="before")
    @classmethod
    def _normalize_booking_mode(cls, value):
        if isinstance(value, str):
            return value.strip().lower() or "simple"
        return "simple" if value is None else value

    @model_validator(mode="after")
    def _validate_event_times(self):
        start = time.fromisoformat(self.start_time)
        end = time.fromisoformat(self.end_time)
        if end <= start:
            raise ValueError("End time must be later than start time.")
        return self


class VendorEventStatusRequest(BaseModel):
    status: str = Field(pattern="^(draft|published|archived|cancelled)$")

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "canceled":
                return "cancelled"
            return normalized
        return value


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

    @field_validator("promotion_name", "internal_description", "applicable_to", "promo_code", mode="before")
    @classmethod
    def _strip_promotion_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_promotion(self) -> "PromotionUpsertRequest":
        if not self.promotion_name:
            raise ValueError("Promotion name is required.")
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
        except ValueError as exc:
            raise ValueError("Promotion dates must use YYYY-MM-DD.") from exc
        if end < start:
            raise ValueError("Promotion end date must be on or after its start date.")
        if self.offer_type == "percentage" and self.discount_value > 100:
            raise ValueError("Percentage discounts cannot exceed 100%.")
        if self.require_promo_code and not self.promo_code:
            raise ValueError("A promo code is required when promo-code restriction is enabled.")
        self.promo_code = self.promo_code.upper() if self.promo_code else None
        return self


class PromotionUpdateRequest(BaseModel):
    promotion_name: str | None = None
    internal_description: str | None = None
    offer_type: str | None = Field(default=None, pattern="^(percentage|fixed_amount|happy_hour|custom_deal)$")
    discount_value: float | None = Field(default=None, ge=0)
    applicable_to: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    recurring_days: list[str] | None = None
    require_promo_code: bool | None = None
    promo_code: str | None = None
    first_time_customers_only: bool | None = None
    minimum_spend: float | None = Field(default=None, ge=0)
    active: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "PromotionUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one promotion field must be provided.")
        if self.promotion_name is not None:
            self.promotion_name = self.promotion_name.strip()
            if not self.promotion_name:
                raise ValueError("Promotion name cannot be empty.")
        if self.promo_code is not None:
            self.promo_code = self.promo_code.strip().upper() or None
        if self.require_promo_code is True and "promo_code" in self.model_fields_set and not self.promo_code:
            raise ValueError("A promo code is required when promo-code restriction is enabled.")
        if self.offer_type == "percentage" and self.discount_value is not None and self.discount_value > 100:
            raise ValueError("Percentage discounts cannot exceed 100%.")
        if self.start_date and self.end_date:
            try:
                if date.fromisoformat(self.end_date) < date.fromisoformat(self.start_date):
                    raise ValueError("Promotion end date must be on or after its start date.")
            except ValueError as exc:
                if "end date" in str(exc):
                    raise
                raise ValueError("Promotion dates must use YYYY-MM-DD.") from exc
        return self


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


class VendorServiceOffer(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    active: bool = True

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_offer_text(cls, value):
        return str(value or "").strip()


class VendorServiceSettings(BaseModel):
    """Common editable settings shared by restaurant, hotel and spa services."""
    name: str = ""
    profile_image_url: str | None = None
    address: str = ""
    city: str = ""
    phone: str = ""
    email: str = ""
    latitude: float | None = None
    longitude: float | None = None
    about: str = ""
    opening_time: str = ""
    closing_time: str = ""
    available_booking_times: list[str] = Field(default_factory=list)
    seating_preferences: list[str] = Field(default_factory=list)
    policy: str = ""
    amenities: list[str] = Field(default_factory=list, max_length=50)
    special_offers: list[VendorServiceOffer] = Field(default_factory=list, max_length=20)
    published: bool | None = None
    model_config = ConfigDict(extra="allow")

    @field_validator("name", "address", "city", "phone", "email", "about", "policy", mode="before")
    @classmethod
    def strip_text(cls, value):
        return str(value or "").strip()

    @field_validator("profile_image_url", mode="before")
    @classmethod
    def normalize_profile_image_url(cls, value):
        normalized = str(value or "").strip()
        return normalized or None

    @field_validator("opening_time", "closing_time", mode="before")
    @classmethod
    def validate_time(cls, value):
        text = str(value or "").strip().upper()
        if not text:
            return ""
        import re
        # Accept older saved values from the previous free-text field and
        # normalize 24-hour input into the new quarter-hour AM/PM contract.
        if " - " in text:
            text = text.split(" - ", 1)[0].strip()
        match_24 = re.fullmatch(r"([01]\d|2[0-3]):(00|15|30|45)", text)
        if match_24:
            from datetime import datetime as _datetime
            return _datetime.strptime(text, "%H:%M").strftime("%I:%M %p")
        if not re.fullmatch(r"(?:0[1-9]|1[0-2]):(?:00|15|30|45) (?:AM|PM)", text):
            raise ValueError("Time must use 12-hour format with 00, 15, 30, or 45 minutes (for example 09:15 AM).")
        return text

    @field_validator("available_booking_times", mode="before")
    @classmethod
    def normalize_booking_times(cls, value):
        values = value if isinstance(value, list) else str(value or "").split(",")
        import re
        from datetime import datetime as _datetime
        normalized = []
        for item in values:
            text = str(item or "").strip().upper()
            if not text:
                continue
            if not re.fullmatch(r"(?:0?[1-9]|1[0-2]):(?:00|15|30|45) (?:AM|PM)", text):
                raise ValueError("Booking times must use 12-hour format with 00, 15, 30, or 45 minutes.")
            normalized.append(_datetime.strptime(text, "%I:%M %p").strftime("%I:%M %p"))
        return list(dict.fromkeys(normalized))

    @field_validator("seating_preferences", mode="before")
    @classmethod
    def normalize_seating_preferences(cls, value):
        values = value if isinstance(value, list) else str(value or "").split(",")
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def validate_coordinates(cls, value, info):
        if value is None or value == "":
            return None
        numeric = float(value)
        limit = 90 if info.field_name == "latitude" else 180
        if not -limit <= numeric <= limit:
            raise ValueError(f"{info.field_name.title()} must be within its valid geographic range.")
        return numeric

    @field_validator("amenities", mode="before")
    @classmethod
    def normalize_amenities(cls, value):
        values = value if isinstance(value, list) else str(value or "").split(",")
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


class VendorSettingsProfileRequest(BaseModel):
    owner_full_name: str = ""
    business_location_label: str | None = None
    business_name: str = ""
    category: str = ""
    categories: list[str] | None = None
    email_address: str = ""
    phone_number: str = ""
    about_business: str = ""
    office_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    place_id: str | None = None
    website: str | None = None
    map_embed_url: str | None = None
    avatar_url: str | None = None
    restaurant_settings: VendorServiceSettings | None = None
    hotel_settings: VendorServiceSettings | None = None
    spa_settings: VendorServiceSettings | None = None

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_account_categories(value)

    @model_validator(mode="after")
    def remove_legacy_event_venue_category(self) -> "VendorSettingsProfileRequest":
        if self.category.strip().casefold() == "event venue":
            self.category = (self.categories or ["Restaurant"])[0]
        return self


class VendorServiceSettingsRequest(BaseModel):
    data: VendorServiceSettings | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_direct_service_payload(cls, value):
        if isinstance(value, dict) and "data" not in value:
            return {"data": value}
        return value

class VendorAmenityCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return str(value or "").strip()


class VendorAmenityCreateResponse(BaseModel):
    service_type: str
    amenity: str
    created: bool
    amenities: list[str] = Field(max_length=50)


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
    new_booking: bool = True
    booking_cancellation: bool = True
    new_review: bool = True
    platform_updates: bool = False


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

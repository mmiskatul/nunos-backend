from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import ListingType


class AIPlannerLocation(BaseModel):
    lat: float | None = None
    lng: float | None = None
    metro_station: str | None = None

    @model_validator(mode="after")
    def validate_location(self) -> "AIPlannerLocation":
        if self.metro_station:
            return self
        if self.lat is not None and self.lng is not None:
            return self
        raise ValueError("Provide either metro_station or lat/lng")


class AIPlanRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mood": "romantic",
                "budget_range": "medium",
                "time_window": "6pm-10pm",
                "location": {"metro_station": "Banani"},
                "preferences": ["restaurant", "spa"],
                "near_metro": True,
                "offers": True,
            }
        }
    )

    mood: str
    budget_range: str
    time_window: str
    location: AIPlannerLocation
    preferences: list[ListingType] = Field(default_factory=list)
    near_metro: bool = True
    offers: bool = False

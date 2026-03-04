from typing import Any

from pydantic import BaseModel, Field


class PlannedEndpointResponse(BaseModel):
    status: str = "planned"
    endpoint: str
    module: str
    description: str
    connected_from: list[str] = Field(default_factory=list)


class GenericPatchRequest(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class StatusUpdateRequest(BaseModel):
    status: str
    note: str | None = None


class MessageCreateRequest(BaseModel):
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BookingCreateRequest(BaseModel):
    provider_id: str
    provider_type: str
    service_id: str | None = None
    room_id: str | None = None
    event_id: str | None = None
    date: str
    time: str
    guests: int = Field(ge=1, le=20)
    notes: str | None = None


class PlanForMeStepRequest(BaseModel):
    value: str | int | bool | dict[str, Any] | list[str]


class AssetUploadRequest(BaseModel):
    asset_url: str
    asset_type: str
    caption: str | None = None


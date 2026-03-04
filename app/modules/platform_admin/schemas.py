from pydantic import BaseModel, Field


class VendorVerificationDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    rejection_reason: str | None = None


class AdminVendorListResponse(BaseModel):
    vendors: list[dict]
    total: int


class UserStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(active|blocked)$")


class AdminUserListResponse(BaseModel):
    users: list[dict]
    total: int

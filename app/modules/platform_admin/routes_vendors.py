from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.platform_admin.deps import get_vendor_repository
from app.modules.platform_admin.schemas import AdminVendorListResponse, VendorVerificationDecisionRequest
from app.modules.vendor.repositories_vendor import VendorRepository

router = APIRouter(prefix="/platform-admin/vendors", tags=["Platform Admin - Vendors (Live)"])


@router.get("", response_model=AdminVendorListResponse)
def list_all_vendors(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    vendor_repo: VendorRepository = Depends(get_vendor_repository),
) -> AdminVendorListResponse:
    vendors = vendor_repo.list_vendors(limit=limit, skip=skip, search=search, status=status_filter)
    total = vendor_repo.count_vendors(search=search, status=status_filter)
    return AdminVendorListResponse(vendors=vendors, total=total)


@router.get("/pending", response_model=AdminVendorListResponse)
def list_pending_vendors(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    vendor_repo: VendorRepository = Depends(get_vendor_repository),
) -> AdminVendorListResponse:
    vendors = vendor_repo.list_by_status("pending_approval", limit=limit, skip=skip)
    total = vendor_repo.count_vendors(status="pending_approval")
    return AdminVendorListResponse(vendors=vendors, total=total)


@router.get("/{vendor_id}", response_model=dict)
def get_vendor_details(
    vendor_id: str,
    vendor_repo: VendorRepository = Depends(get_vendor_repository),
) -> dict:
    application = vendor_repo.get_vendor_application(vendor_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found.")
    return application


@router.get("/{vendor_id}/sections", response_model=dict)
def get_vendor_sections(
    vendor_id: str,
    vendor_repo: VendorRepository = Depends(get_vendor_repository),
) -> dict:
    vendor = vendor_repo.get_by_id(vendor_id)
    if not vendor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found.")
    return vendor_repo.get_vendor_sections(vendor_id)


@router.patch("/{vendor_id}/verification", response_model=dict)
def decide_vendor_verification(
    vendor_id: str,
    payload: VendorVerificationDecisionRequest,
    vendor_repo: VendorRepository = Depends(get_vendor_repository),
) -> dict:
    updated = vendor_repo.set_verification_decision(
        vendor_id=vendor_id, decision=payload.decision, reason=payload.rejection_reason
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found.")
    return updated

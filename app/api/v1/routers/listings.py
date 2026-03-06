from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user_id, get_listing_service
from app.core.responses import envelope
from app.core.serializers import to_jsonable
from app.domain.enums import ListingType
from app.models.listing import ListingSearchQuery, ReviewCreateRequest
from app.services.listing_service import ListingService

router = APIRouter(prefix="/listings", tags=["Listings"])


@router.get("")
async def search_listings(
    q: str | None = Query(default=None),
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
    radius: int = Query(default=3000, ge=100, le=30000),
    budget: int | None = Query(default=None, ge=1, le=5),
    near_metro: str | None = Query(default=None),
    offers: bool | None = Query(default=None),
    rating: float | None = Query(default=None, ge=0, le=5),
    type: list[ListingType] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    service: ListingService = Depends(get_listing_service),
):
    payload = ListingSearchQuery(
        q=q,
        lat=lat,
        lng=lng,
        radius_meters=radius,
        budget=budget,
        near_metro=near_metro,
        offers=offers,
        rating=rating,
        types=type,
        limit=limit,
    )
    listings = await service.search(payload)
    return envelope(to_jsonable(listings), meta={"count": len(listings)})


@router.get("/{listing_id}")
async def get_listing_detail(listing_id: str, service: ListingService = Depends(get_listing_service)):
    listing = await service.get_listing_detail(listing_id)
    return envelope(to_jsonable(listing))


@router.post("/{listing_id}/reviews")
async def create_review(
    listing_id: str,
    payload: ReviewCreateRequest,
    user_id: str = Depends(get_current_user_id),
    service: ListingService = Depends(get_listing_service),
):
    review = await service.create_review(user_id, listing_id, payload)
    return envelope(to_jsonable(review))


@router.post("/{listing_id}/favorite")
async def add_favorite(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
    service: ListingService = Depends(get_listing_service),
):
    await service.add_favorite(user_id, listing_id)
    return envelope({"message": "Added to favorites"})


@router.delete("/{listing_id}/favorite")
async def remove_favorite(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
    service: ListingService = Depends(get_listing_service),
):
    await service.remove_favorite(user_id, listing_id)
    return envelope({"message": "Removed from favorites"})

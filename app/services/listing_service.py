from bson import ObjectId
from fastapi import HTTPException, status

from app.models.listing import ListingSearchQuery, ReviewCreateRequest
from app.repositories.favorite_repository import FavoriteRepository
from app.repositories.listing_repository import ListingRepository
from app.repositories.review_repository import ReviewRepository


class ListingService:
    def __init__(
        self,
        listing_repo: ListingRepository,
        review_repo: ReviewRepository,
        favorite_repo: FavoriteRepository,
    ):
        self.listing_repo = listing_repo
        self.review_repo = review_repo
        self.favorite_repo = favorite_repo

    async def search(self, query: ListingSearchQuery) -> list[dict]:
        mongo_query: dict = {}
        if query.q:
            mongo_query["$text"] = {"$search": query.q}
        if query.lat is not None and query.lng is not None:
            mongo_query["location"] = {
                "$near": {
                    "$geometry": {"type": "Point", "coordinates": [query.lng, query.lat]},
                    "$maxDistance": query.radius_meters,
                }
            }
        if query.budget is not None:
            mongo_query["price_level"] = {"$lte": query.budget}
        if query.near_metro:
            mongo_query["near_metro_station"] = query.near_metro
        if query.offers is not None:
            mongo_query["has_offers"] = query.offers
        if query.rating is not None:
            mongo_query["rating_summary.average"] = {"$gte": query.rating}
        if query.types:
            mongo_query["type"] = {"$in": [value.value for value in query.types]}

        return await self.listing_repo.search(mongo_query, query.limit)

    async def get_listing_detail(self, listing_id: str) -> dict:
        listing = await self.listing_repo.get_by_id(listing_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

        reviews = await self.review_repo.list_for_listing(listing_id)
        listing["reviews"] = reviews
        return listing

    async def create_review(self, user_id: str, listing_id: str, payload: ReviewCreateRequest) -> dict:
        listing = await self.listing_repo.get_by_id(listing_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

        review = await self.review_repo.create(
            {
                "user_id": ObjectId(user_id),
                "listing_id": ObjectId(listing_id),
                "rating": payload.rating,
                "comment": payload.comment,
            }
        )

        avg, count = await self.review_repo.rating_aggregate(listing_id)
        await self.listing_repo.update_rating_summary(listing_id, avg, count)
        return review

    async def add_favorite(self, user_id: str, listing_id: str) -> None:
        if not await self.listing_repo.get_by_id(listing_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
        await self.favorite_repo.add(user_id, listing_id)

    async def remove_favorite(self, user_id: str, listing_id: str) -> None:
        await self.favorite_repo.remove(user_id, listing_id)

    async def list_favorites(self, user_id: str) -> list[dict]:
        listing_ids = await self.favorite_repo.list_listing_ids(user_id)
        favorites: list[dict] = []
        for listing_id in listing_ids:
            listing = await self.listing_repo.get_by_id(listing_id)
            if listing:
                favorites.append(listing)
        return favorites

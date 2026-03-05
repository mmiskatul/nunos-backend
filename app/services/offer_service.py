from datetime import UTC, datetime

from app.models.listing import PromoValidationRequest, PromoValidationResult
from app.repositories.offer_repository import OfferRepository


class OfferService:
    def __init__(self, offer_repo: OfferRepository):
        self.offer_repo = offer_repo

    async def validate_promo(self, payload: PromoValidationRequest) -> PromoValidationResult:
        offer = await self.offer_repo.validate_promo(payload.listing_id, payload.promo_code, datetime.now(UTC))
        if not offer:
            return PromoValidationResult(valid=False, message="Promo code is invalid or unavailable")

        if offer.get("require_code") and offer.get("promo_code") != payload.promo_code:
            return PromoValidationResult(valid=False, message="Promo code required")

        return PromoValidationResult(
            valid=True,
            message="Promo applied",
            discount_percent=offer.get("discount_percent"),
            offer_id=str(offer["_id"]),
        )

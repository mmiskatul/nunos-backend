from fastapi import APIRouter, Depends

from app.api.deps import get_offer_service
from app.core.responses import envelope
from app.models.listing import PromoValidationRequest
from app.services.offer_service import OfferService

router = APIRouter(prefix="/offers", tags=["Offers"])


@router.post("/validate")
async def validate_offer(payload: PromoValidationRequest, service: OfferService = Depends(get_offer_service)):
    result = await service.validate_promo(payload)
    return envelope(result.model_dump())

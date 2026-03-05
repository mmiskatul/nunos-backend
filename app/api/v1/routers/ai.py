from fastapi import APIRouter, Depends

from app.api.deps import get_ai_service
from app.core.responses import envelope
from app.models.ai import AIPlanRequest
from app.services.ai_service import AIPlannerService

router = APIRouter(prefix="/ai", tags=["AI Concierge"])


@router.post("/plan")
async def generate_plan(payload: AIPlanRequest, service: AIPlannerService = Depends(get_ai_service)):
    plan = await service.create_plan(payload)
    return envelope(plan.model_dump(mode="json"))

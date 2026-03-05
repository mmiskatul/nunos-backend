from fastapi import HTTPException, status
from pydantic import ValidationError

from app.ai.client import LLMClient
from app.ai.prompt_templates import SYSTEM_PROMPT, build_planner_prompt
from app.ai.schemas import AIPlan
from app.domain.enums import ListingType
from app.models.ai import AIPlanRequest
from app.repositories.listing_repository import ListingRepository


class AIPlannerService:
    def __init__(self, listing_repo: ListingRepository, llm_client: LLMClient):
        self.listing_repo = listing_repo
        self.llm_client = llm_client

    async def create_plan(self, payload: AIPlanRequest) -> AIPlan:
        preferences = payload.preferences or [
            ListingType.restaurant,
            ListingType.event,
            ListingType.spa,
            ListingType.hotel,
        ]

        candidates: dict[str, list[dict]] = {}
        for listing_type in preferences:
            docs = await self.listing_repo.top_by_type(
                listing_type.value,
                limit=5,
                near_metro=payload.near_metro,
                offers=payload.offers,
            )
            candidates[listing_type.value] = [
                {
                    "id": str(doc["_id"]),
                    "name": doc["name"],
                    "type": doc["type"],
                    "near_metro_station": doc.get("near_metro_station"),
                    "price_level": doc.get("price_level"),
                    "has_offers": doc.get("has_offers", False),
                    "rating": doc.get("rating_summary", {}).get("average", 0),
                }
                for doc in docs
            ]

        user_input = payload.model_dump(mode="json")
        prompt = build_planner_prompt(user_input, candidates)

        try:
            llm_json = await self.llm_client.generate_json(prompt=prompt, system_prompt=SYSTEM_PROMPT)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI provider failed: {exc}",
            ) from exc

        try:
            return AIPlan.model_validate(llm_json)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Invalid AI output: {exc}") from exc

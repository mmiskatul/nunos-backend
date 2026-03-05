import json
from typing import Protocol

import httpx

from app.core.config import Settings


class LLMClient(Protocol):
    async def generate_json(self, *, prompt: str, system_prompt: str) -> dict:
        ...


class OpenAILLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate_json(self, *, prompt: str, system_prompt: str) -> dict:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.openai_model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
        }

        async with httpx.AsyncClient(timeout=self.settings.openai_timeout_seconds) as client:
            response = await client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        text = _extract_text(body)
        return json.loads(text)


class StubLLMClient:
    async def generate_json(self, *, prompt: str, system_prompt: str) -> dict:
        _ = prompt, system_prompt
        return {
            "summary": "A balanced evening plan near metro with offers.",
            "estimated_budget": "medium",
            "steps": [
                {
                    "time": "18:00",
                    "title": "Arrive near metro station",
                    "listing_id": None,
                    "listing_name": None,
                    "note": "Start with a short walk and coffee",
                }
            ],
            "booking_suggestions": [],
            "generated_at": "2026-03-06T00:00:00Z",
        }


def _extract_text(body: dict) -> str:
    for item in body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "{}")
    return "{}"

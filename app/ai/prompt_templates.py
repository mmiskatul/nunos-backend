import json

SYSTEM_PROMPT = """
You are Nuno Concierge AI. You must return strict JSON only.
No markdown and no extra keys.
""".strip()


def build_planner_prompt(user_input: dict, candidates: dict[str, list[dict]]) -> str:
    return (
        "Create a personalized city plan using available candidates. "
        "Return JSON object with keys: summary, estimated_budget, steps, booking_suggestions, generated_at.\n"
        f"USER_INPUT:\n{json.dumps(user_input, indent=2, default=str)}\n"
        f"CANDIDATES:\n{json.dumps(candidates, indent=2, default=str)}"
    )

from app.repositories.user_repository import UserRepository


class LoyaltyService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_loyalty(self, user_id: str) -> dict:
        user = await self.user_repo.find_by_id(user_id)
        points = int(user.get("points_balance", 0)) if user else 0
        tier = "bronze"
        if points >= 500:
            tier = "gold"
        elif points >= 200:
            tier = "silver"
        return {"points_balance": points, "tier": tier}

from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.modules.customer.repositories_customer import CustomerRepository


class CustomerService:
    def __init__(self, repo: CustomerRepository):
        self.repo = repo

    def get_restaurant_or_404(self, customer_id: str, restaurant_id: str) -> dict:
        try:
            row = self.repo.get_restaurant_details(customer_id, restaurant_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found.") from exc
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found.")
        return row

    def get_booking_or_404(self, customer_id: str, booking_id: str) -> dict:
        try:
            row = self.repo.get_customer_booking(customer_id, booking_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.") from exc
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
        return row

    def get_event_or_404(self, customer_id: str, event_id: str) -> dict:
        try:
            row = self.repo.get_event_details(customer_id, event_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.") from exc
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
        return row


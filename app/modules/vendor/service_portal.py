from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.modules.vendor.repositories_portal import VendorPortalRepository


class VendorPortalService:
    def __init__(self, repo: VendorPortalRepository):
        self.repo = repo

    def initialize(self, vendor_id: str) -> None:
        self.repo.ensure_seed_data(vendor_id)

    def list_bookings(self, vendor_id: str, **kwargs):
        self.initialize(vendor_id)
        return self.repo.list_bookings(vendor_id, **kwargs)

    def get_booking_or_404(self, vendor_id: str, booking_id: str):
        self.initialize(vendor_id)
        try:
            booking = self.repo.get_booking(vendor_id, booking_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.") from exc
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
        return booking

    def get_room_or_404(self, vendor_id: str, room_id: str):
        self.initialize(vendor_id)
        try:
            room = self.repo.get_room(vendor_id, room_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.") from exc
        if not room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")
        return room

    def get_service_or_404(self, vendor_id: str, service_id: str):
        self.initialize(vendor_id)
        try:
            service = self.repo.get_service(vendor_id, service_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.") from exc
        if not service:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")
        return service

    def get_promotion_or_404(self, vendor_id: str, promotion_id: str):
        self.initialize(vendor_id)
        try:
            promotion = self.repo.get_promotion(vendor_id, promotion_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.") from exc
        if not promotion:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.")
        return promotion

    def get_support_ticket_or_404(self, vendor_id: str, ticket_id: str):
        self.initialize(vendor_id)
        try:
            ticket = self.repo.get_support_ticket(vendor_id, ticket_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found.") from exc
        if not ticket:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found.")
        return ticket


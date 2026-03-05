from fastapi import HTTPException, status

from app.domain.enums import BookingType
from app.services.bookings.base import BookingStrategy
from app.services.bookings.room_strategy import RoomBookingStrategy
from app.services.bookings.spa_strategy import SpaBookingStrategy
from app.services.bookings.table_strategy import TableBookingStrategy
from app.services.bookings.ticket_strategy import TicketBookingStrategy


class BookingStrategyFactory:
    def __init__(self):
        self._registry: dict[str, BookingStrategy] = {
            BookingType.table.value: TableBookingStrategy(),
            BookingType.room.value: RoomBookingStrategy(),
            BookingType.spa.value: SpaBookingStrategy(),
            BookingType.ticket.value: TicketBookingStrategy(),
        }

    def get(self, booking_type: str) -> BookingStrategy:
        strategy = self._registry.get(booking_type)
        if not strategy:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported booking_type")
        return strategy

from enum import StrEnum


class ListingType(StrEnum):
    restaurant = "restaurant"
    hotel = "hotel"
    spa = "spa"
    event = "event"


class BookingType(StrEnum):
    table = "table"
    room = "room"
    spa = "spa"
    ticket = "ticket"


class BookingStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    rescheduled = "rescheduled"

from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.modules.customer.deps import get_customer_service
from app.modules.customer.schemas_live import (
    CustomerAvailabilityRequest,
    CustomerBookingCancelRequest,
    CustomerBookingCreateRequest,
    CustomerBookingQuoteRequest,
    CustomerBookingRescheduleRequest,
)
from app.modules.customer.service_customer import CustomerService
from app.modules.schemas import (
    GenericPatchRequest,
    PlanForMeStepRequest,
    PlannedEndpointResponse,
)

router = APIRouter(prefix="/customer")


def _planned(endpoint: str, description: str, connected_from: list[str]) -> PlannedEndpointResponse:
    return PlannedEndpointResponse(
        endpoint=endpoint,
        module="customer",
        description=description,
        connected_from=connected_from,
    )


@router.get("/home", tags=["Customer - Home"])
def get_home_feed(
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    try:
        return customer_service.repo.get_home_feed(current_user["id"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load home feed: {exc}",
        ) from exc


@router.get("/location/current", tags=["Customer - Home"], response_model=PlannedEndpointResponse)
def get_current_location() -> PlannedEndpointResponse:
    return _planned("/customer/location/current", "Get active customer location.", ["Home", "Search"])


@router.patch("/location/current", tags=["Customer - Home"], response_model=PlannedEndpointResponse)
def update_current_location(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/customer/location/current", "Update active customer location.", ["Home", "Search"])


@router.get("/notifications/unread-count", tags=["Customer - Home"], response_model=PlannedEndpointResponse)
def get_unread_notification_count() -> PlannedEndpointResponse:
    return _planned(
        "/customer/notifications/unread-count",
        "Fetch unread notification count for bell icon badge.",
        ["Home Header", "Profile"],
    )


@router.get("/notifications", tags=["Customer - Home"], response_model=PlannedEndpointResponse)
def list_notifications() -> PlannedEndpointResponse:
    return _planned("/customer/notifications", "List customer notifications.", ["Notification Center"])


@router.post("/plan-for-me/sessions", tags=["Customer - Plan"], response_model=PlannedEndpointResponse)
def create_plan_session() -> PlannedEndpointResponse:
    return _planned(
        "/customer/plan-for-me/sessions",
        "Start guided planning wizard session.",
        ["Plan for me: companions"],
    )


@router.patch(
    "/plan-for-me/sessions/{session_id}/companions",
    tags=["Customer - Plan"],
    response_model=PlannedEndpointResponse,
)
def set_plan_companions(session_id: str, payload: PlanForMeStepRequest) -> PlannedEndpointResponse:
    _ = (session_id, payload)
    return _planned(
        "/customer/plan-for-me/sessions/{session_id}/companions",
        "Store selected travel companions.",
        ["Plan for me: companions"],
    )


@router.patch("/plan-for-me/sessions/{session_id}/mood", tags=["Customer - Plan"], response_model=PlannedEndpointResponse)
def set_plan_mood(session_id: str, payload: PlanForMeStepRequest) -> PlannedEndpointResponse:
    _ = (session_id, payload)
    return _planned(
        "/customer/plan-for-me/sessions/{session_id}/mood",
        "Store mood/style selection (chill, party, active, fancy).",
        ["Plan for me: style"],
    )


@router.patch(
    "/plan-for-me/sessions/{session_id}/budget",
    tags=["Customer - Plan"],
    response_model=PlannedEndpointResponse,
)
def set_plan_budget(session_id: str, payload: PlanForMeStepRequest) -> PlannedEndpointResponse:
    _ = (session_id, payload)
    return _planned(
        "/customer/plan-for-me/sessions/{session_id}/budget",
        "Store budget range selection.",
        ["Plan for me: budget"],
    )


@router.patch(
    "/plan-for-me/sessions/{session_id}/preferences",
    tags=["Customer - Plan"],
    response_model=PlannedEndpointResponse,
)
def set_plan_preferences(session_id: str, payload: PlanForMeStepRequest) -> PlannedEndpointResponse:
    _ = (session_id, payload)
    return _planned(
        "/customer/plan-for-me/sessions/{session_id}/preferences",
        "Store final preferences like area and vouchers toggle.",
        ["Plan for me: final touches"],
    )


@router.post(
    "/plan-for-me/sessions/{session_id}/reveal",
    tags=["Customer - Plan"],
    response_model=PlannedEndpointResponse,
)
def reveal_plan(session_id: str) -> PlannedEndpointResponse:
    _ = session_id
    return _planned(
        "/customer/plan-for-me/sessions/{session_id}/reveal",
        "Generate recommendations from wizard selections.",
        ["Plan for me: reveal plan"],
    )


@router.get("/categories", tags=["Customer - Discover"], response_model=PlannedEndpointResponse)
def list_discovery_categories() -> PlannedEndpointResponse:
    return _planned(
        "/customer/categories",
        "Get categories with counts for Restaurants, Events, Spas, Hotels.",
        ["Search browse by category", "Home quick access"],
    )


@router.get("/restaurants", tags=["Customer - Restaurants"])
def list_restaurants(
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    open_now: bool | None = Query(default=None),
    top_rated: bool | None = Query(default=None),
    offers: bool | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    return customer_service.repo.list_restaurants(
        customer_id=current_user["id"],
        limit=limit,
        skip=skip,
        search=search,
        open_now=open_now,
        top_rated=top_rated,
        with_offers=offers,
    )


@router.get("/restaurants/{restaurant_id}", tags=["Customer - Restaurants"])
def get_restaurant_details(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    return customer_service.get_restaurant_or_404(current_user["id"], restaurant_id)


@router.get("/restaurants/{restaurant_id}/menu", tags=["Customer - Restaurants"])
def get_restaurant_menu(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    _ = current_user
    try:
        items = customer_service.repo.list_restaurant_assets(restaurant_id, "menu")
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found.") from exc
    return {"items": items}


@router.get("/restaurants/{restaurant_id}/gallery", tags=["Customer - Restaurants"])
def get_restaurant_gallery(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    _ = current_user
    try:
        items = customer_service.repo.list_restaurant_assets(restaurant_id, "gallery")
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found.") from exc
    return {"items": items}


@router.get("/restaurants/{restaurant_id}/offers", tags=["Customer - Restaurants"])
def get_restaurant_offers(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    _ = current_user
    try:
        items = customer_service.repo.list_restaurant_offers(restaurant_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found.") from exc
    return {"items": items}


@router.get("/spas", tags=["Customer - Spa"], response_model=PlannedEndpointResponse)
def list_spas() -> PlannedEndpointResponse:
    return _planned("/customer/spas", "Spa list with filters and sorting.", ["Spa list screen"])


@router.get("/spas/{spa_id}", tags=["Customer - Spa"], response_model=PlannedEndpointResponse)
def get_spa_details(spa_id: str) -> PlannedEndpointResponse:
    _ = spa_id
    return _planned("/customer/spas/{spa_id}", "Spa detail with overview and amenities.", ["Spa details screen"])


@router.get("/spas/{spa_id}/menu", tags=["Customer - Spa"], response_model=PlannedEndpointResponse)
def get_spa_menu(spa_id: str) -> PlannedEndpointResponse:
    _ = spa_id
    return _planned("/customer/spas/{spa_id}/menu", "Spa services/menu media.", ["Spa menu tab"])


@router.get("/spas/{spa_id}/gallery", tags=["Customer - Spa"], response_model=PlannedEndpointResponse)
def get_spa_gallery(spa_id: str) -> PlannedEndpointResponse:
    _ = spa_id
    return _planned("/customer/spas/{spa_id}/gallery", "Spa gallery media.", ["Spa gallery tab"])


@router.get("/spas/{spa_id}/offers", tags=["Customer - Spa"], response_model=PlannedEndpointResponse)
def get_spa_offers(spa_id: str) -> PlannedEndpointResponse:
    _ = spa_id
    return _planned("/customer/spas/{spa_id}/offers", "Spa offers and deals.", ["Spa offers tab"])


@router.get("/events", tags=["Customer - Events"], response_model=PlannedEndpointResponse)
def list_events() -> PlannedEndpointResponse:
    return _planned("/customer/events", "Event list by category and date filters.", ["Events list screen"])


@router.get("/events/{event_id}", tags=["Customer - Events"], response_model=PlannedEndpointResponse)
def get_event_details(event_id: str) -> PlannedEndpointResponse:
    _ = event_id
    return _planned("/customer/events/{event_id}", "Event details including artist info and directions.", ["Event details"])


@router.get("/events/{event_id}/directions", tags=["Customer - Events"], response_model=PlannedEndpointResponse)
def get_event_directions(event_id: str) -> PlannedEndpointResponse:
    _ = event_id
    return _planned("/customer/events/{event_id}/directions", "Map directions deep link payload.", ["Event details"])


@router.get("/hotels", tags=["Customer - Hotels"], response_model=PlannedEndpointResponse)
def list_hotels() -> PlannedEndpointResponse:
    return _planned("/customer/hotels", "Hotel list with map/list mode and filters.", ["Hotels list"])


@router.get("/hotels/{hotel_id}", tags=["Customer - Hotels"], response_model=PlannedEndpointResponse)
def get_hotel_details(hotel_id: str) -> PlannedEndpointResponse:
    _ = hotel_id
    return _planned("/customer/hotels/{hotel_id}", "Hotel detail with rooms, gallery, reviews, offers.", ["Hotel details"])


@router.get("/hotels/{hotel_id}/rooms", tags=["Customer - Hotels"], response_model=PlannedEndpointResponse)
def list_hotel_rooms(hotel_id: str) -> PlannedEndpointResponse:
    _ = hotel_id
    return _planned("/customer/hotels/{hotel_id}/rooms", "List hotel room inventory by date and occupancy.", ["Rooms list"])


@router.get("/hotels/rooms/{room_id}", tags=["Customer - Hotels"], response_model=PlannedEndpointResponse)
def get_hotel_room_details(room_id: str) -> PlannedEndpointResponse:
    _ = room_id
    return _planned("/customer/hotels/rooms/{room_id}", "Room detail with amenities, price breakdown, policies.", ["Room details"])


@router.get("/search", tags=["Customer - Search"], response_model=PlannedEndpointResponse)
def global_search() -> PlannedEndpointResponse:
    return _planned("/customer/search", "Global search across restaurants/events/spas/hotels.", ["Search screen"])


@router.get("/search/recent", tags=["Customer - Search"], response_model=PlannedEndpointResponse)
def list_recent_searches() -> PlannedEndpointResponse:
    return _planned("/customer/search/recent", "Fetch recent search history.", ["Search recent list"])


@router.delete("/search/recent", tags=["Customer - Search"], response_model=PlannedEndpointResponse)
def clear_recent_searches() -> PlannedEndpointResponse:
    return _planned("/customer/search/recent", "Clear recent searches.", ["Search recent list"])


@router.get("/map/pins", tags=["Customer - Search"])
def get_map_pins(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    return {"items": customer_service.repo.map_pins(current_user["id"], limit=limit)}


@router.get("/map/highlight", tags=["Customer - Search"])
def get_map_highlight_card(
    restaurant_id: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    try:
        item = customer_service.repo.map_highlight(current_user["id"], restaurant_id=restaurant_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found.") from exc
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No highlighted venue found.")
    return item


@router.get("/filters", tags=["Customer - Search"], response_model=PlannedEndpointResponse)
def get_available_filters() -> PlannedEndpointResponse:
    return _planned("/customer/filters", "Get filter chips/options by category.", ["Map", "Lists"])


@router.get("/bookings/availability", tags=["Customer - Bookings"])
def get_booking_availability(
    provider_id: str,
    date: str,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    _ = current_user
    payload = CustomerAvailabilityRequest(provider_id=provider_id, date=date)
    try:
        return customer_service.repo.get_booking_availability(payload.provider_id, payload.date)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found.") from exc


@router.post("/bookings/quote", tags=["Customer - Bookings"])
def get_booking_quote(
    payload: CustomerBookingQuoteRequest,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    _ = current_user
    try:
        return customer_service.repo.get_booking_quote(
            provider_id=payload.provider_id,
            provider_type=payload.provider_type,
            guests=payload.guests,
            date=payload.date,
            time=payload.time,
            seating_preference=payload.seating_preference,
        )
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/bookings", tags=["Customer - Bookings"])
def create_booking(
    payload: CustomerBookingCreateRequest,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    try:
        return customer_service.repo.create_booking(
            customer_id=current_user["id"],
            provider_id=payload.provider_id,
            provider_type=payload.provider_type,
            date=payload.date,
            time=payload.time,
            guests=payload.guests,
            seating_preference=payload.seating_preference,
            special_notes=payload.special_notes,
            auto_confirm=payload.auto_confirm,
        )
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/bookings", tags=["Customer - Bookings"])
def list_my_bookings(
    limit: int = Query(default=20, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    return customer_service.repo.list_customer_bookings(
        customer_id=current_user["id"],
        limit=limit,
        skip=skip,
    )


@router.get("/bookings/{booking_id}", tags=["Customer - Bookings"])
def get_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    return customer_service.get_booking_or_404(current_user["id"], booking_id)


@router.post("/bookings/{booking_id}/confirm", tags=["Customer - Bookings"])
def confirm_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    try:
        updated = customer_service.repo.confirm_booking(current_user["id"], booking_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.") from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return updated


@router.patch("/bookings/{booking_id}/cancel", tags=["Customer - Bookings"])
def cancel_booking(
    booking_id: str,
    payload: CustomerBookingCancelRequest,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    try:
        updated = customer_service.repo.cancel_booking(current_user["id"], booking_id, payload.reason)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.") from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return updated


@router.patch("/bookings/{booking_id}/reschedule", tags=["Customer - Bookings"])
def reschedule_booking(
    booking_id: str,
    payload: CustomerBookingRescheduleRequest,
    current_user: dict = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
) -> dict:
    try:
        updated = customer_service.repo.reschedule_booking(
            customer_id=current_user["id"],
            booking_id=booking_id,
            date=payload.date,
            time=payload.time,
            note=payload.note,
        )
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return updated


@router.get("/saved", tags=["Customer - Saved"], response_model=PlannedEndpointResponse)
def list_saved_items() -> PlannedEndpointResponse:
    return _planned("/customer/saved", "List all saved entities grouped by type.", ["Saved tab"])


@router.post("/saved/{entity_type}/{entity_id}", tags=["Customer - Saved"], response_model=PlannedEndpointResponse)
def add_saved_item(entity_type: str, entity_id: str) -> PlannedEndpointResponse:
    _ = (entity_type, entity_id)
    return _planned("/customer/saved/{entity_type}/{entity_id}", "Save an entity.", ["Cards with favorite icon"])


@router.delete("/saved/{entity_type}/{entity_id}", tags=["Customer - Saved"], response_model=PlannedEndpointResponse)
def remove_saved_item(entity_type: str, entity_id: str) -> PlannedEndpointResponse:
    _ = (entity_type, entity_id)
    return _planned("/customer/saved/{entity_type}/{entity_id}", "Unsave an entity.", ["Saved tab", "Cards with favorite icon"])


@router.get("/profile", tags=["Customer - Profile"], response_model=PlannedEndpointResponse)
def get_customer_profile() -> PlannedEndpointResponse:
    return _planned("/customer/profile", "Get profile summary, points, toggles.", ["Profile tab"])


@router.patch("/profile", tags=["Customer - Profile"], response_model=PlannedEndpointResponse)
def update_customer_profile(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/customer/profile", "Update profile basic information.", ["Profile > Edit profile"])


@router.patch(
    "/profile/notification-preferences",
    tags=["Customer - Profile"],
    response_model=PlannedEndpointResponse,
)
def update_customer_notification_preferences(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned(
        "/customer/profile/notification-preferences",
        "Toggle booking reminders and nearby events notifications.",
        ["Profile notification toggles"],
    )


@router.get("/points/summary", tags=["Customer - Profile"], response_model=PlannedEndpointResponse)
def get_points_summary() -> PlannedEndpointResponse:
    return _planned("/customer/points/summary", "Get loyalty points summary.", ["Profile points card"])

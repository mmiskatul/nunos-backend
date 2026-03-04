from fastapi import APIRouter

from app.modules.schemas import (
    BookingCreateRequest,
    GenericPatchRequest,
    MessageCreateRequest,
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


@router.get("/home", tags=["Customer - Home"], response_model=PlannedEndpointResponse)
def get_home_feed() -> PlannedEndpointResponse:
    return _planned(
        "/customer/home",
        "Home composition endpoint for hero, quick access, trending, and featured sections.",
        ["Home Screen"],
    )


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


@router.get("/restaurants", tags=["Customer - Restaurants"], response_model=PlannedEndpointResponse)
def list_restaurants() -> PlannedEndpointResponse:
    return _planned("/customer/restaurants", "Restaurant list with filters, sort, and pagination.", ["Dining list", "Map"])


@router.get("/restaurants/{restaurant_id}", tags=["Customer - Restaurants"], response_model=PlannedEndpointResponse)
def get_restaurant_details(restaurant_id: str) -> PlannedEndpointResponse:
    _ = restaurant_id
    return _planned(
        "/customer/restaurants/{restaurant_id}",
        "Restaurant detail with overview, reviews, amenities, open hours.",
        ["Restaurant details screen"],
    )


@router.get("/restaurants/{restaurant_id}/menu", tags=["Customer - Restaurants"], response_model=PlannedEndpointResponse)
def get_restaurant_menu(restaurant_id: str) -> PlannedEndpointResponse:
    _ = restaurant_id
    return _planned("/customer/restaurants/{restaurant_id}/menu", "Menu media list for restaurant.", ["Restaurant menu tab"])


@router.get("/restaurants/{restaurant_id}/gallery", tags=["Customer - Restaurants"], response_model=PlannedEndpointResponse)
def get_restaurant_gallery(restaurant_id: str) -> PlannedEndpointResponse:
    _ = restaurant_id
    return _planned(
        "/customer/restaurants/{restaurant_id}/gallery",
        "Gallery media list for restaurant.",
        ["Restaurant gallery tab"],
    )


@router.get("/restaurants/{restaurant_id}/offers", tags=["Customer - Restaurants"], response_model=PlannedEndpointResponse)
def get_restaurant_offers(restaurant_id: str) -> PlannedEndpointResponse:
    _ = restaurant_id
    return _planned("/customer/restaurants/{restaurant_id}/offers", "Active offers for restaurant.", ["Restaurant offers tab"])


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


@router.get("/map/pins", tags=["Customer - Search"], response_model=PlannedEndpointResponse)
def get_map_pins() -> PlannedEndpointResponse:
    return _planned("/customer/map/pins", "Get map markers with filter support.", ["Map discovery"])


@router.get("/map/highlight", tags=["Customer - Search"], response_model=PlannedEndpointResponse)
def get_map_highlight_card() -> PlannedEndpointResponse:
    return _planned("/customer/map/highlight", "Bottom-sheet highlighted venue card for selected pin.", ["Map discovery"])


@router.get("/filters", tags=["Customer - Search"], response_model=PlannedEndpointResponse)
def get_available_filters() -> PlannedEndpointResponse:
    return _planned("/customer/filters", "Get filter chips/options by category.", ["Map", "Lists"])


@router.get("/bookings/availability", tags=["Customer - Bookings"], response_model=PlannedEndpointResponse)
def get_booking_availability() -> PlannedEndpointResponse:
    return _planned("/customer/bookings/availability", "Get date/time slot availability for a provider.", ["Book now/table"])


@router.post("/bookings/quote", tags=["Customer - Bookings"], response_model=PlannedEndpointResponse)
def get_booking_quote(payload: BookingCreateRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/customer/bookings/quote", "Calculate pricing/fees before booking confirmation.", ["Booking summary"])


@router.post("/bookings", tags=["Customer - Bookings"], response_model=PlannedEndpointResponse)
def create_booking(payload: BookingCreateRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/customer/bookings", "Create booking for restaurant/spa/hotel/event.", ["Confirm booking"])


@router.get("/bookings", tags=["Customer - Bookings"], response_model=PlannedEndpointResponse)
def list_my_bookings() -> PlannedEndpointResponse:
    return _planned("/customer/bookings", "List customer bookings history and upcoming.", ["Profile > My bookings"])


@router.get("/bookings/{booking_id}", tags=["Customer - Bookings"], response_model=PlannedEndpointResponse)
def get_booking(booking_id: str) -> PlannedEndpointResponse:
    _ = booking_id
    return _planned("/customer/bookings/{booking_id}", "Get booking details.", ["Booking details", "Booking confirmed"])


@router.post("/bookings/{booking_id}/confirm", tags=["Customer - Bookings"], response_model=PlannedEndpointResponse)
def confirm_booking(booking_id: str) -> PlannedEndpointResponse:
    _ = booking_id
    return _planned("/customer/bookings/{booking_id}/confirm", "Finalize booking from summary screen.", ["Confirm booking"])


@router.patch("/bookings/{booking_id}/cancel", tags=["Customer - Bookings"], response_model=PlannedEndpointResponse)
def cancel_booking(booking_id: str, payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = (booking_id, payload)
    return _planned("/customer/bookings/{booking_id}/cancel", "Cancel booking with reason.", ["Booking details"])


@router.patch("/bookings/{booking_id}/reschedule", tags=["Customer - Bookings"], response_model=PlannedEndpointResponse)
def reschedule_booking(booking_id: str, payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = (booking_id, payload)
    return _planned("/customer/bookings/{booking_id}/reschedule", "Reschedule booking date/time.", ["Booking details"])


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


@router.get("/ai-concierge/sessions", tags=["Customer - AI Chat"], response_model=PlannedEndpointResponse)
def list_ai_sessions() -> PlannedEndpointResponse:
    return _planned("/customer/ai-concierge/sessions", "List customer AI concierge sessions.", ["Chat tab"])


@router.post("/ai-concierge/sessions", tags=["Customer - AI Chat"], response_model=PlannedEndpointResponse)
def create_ai_session() -> PlannedEndpointResponse:
    return _planned("/customer/ai-concierge/sessions", "Start a new AI concierge session.", ["Chat tab"])


@router.get("/ai-concierge/sessions/{session_id}/messages", tags=["Customer - AI Chat"], response_model=PlannedEndpointResponse)
def list_ai_messages(session_id: str) -> PlannedEndpointResponse:
    _ = session_id
    return _planned("/customer/ai-concierge/sessions/{session_id}/messages", "Get chat messages in a session.", ["Chat conversation"])


@router.post("/ai-concierge/sessions/{session_id}/messages", tags=["Customer - AI Chat"], response_model=PlannedEndpointResponse)
def send_ai_message(session_id: str, payload: MessageCreateRequest) -> PlannedEndpointResponse:
    _ = (session_id, payload)
    return _planned("/customer/ai-concierge/sessions/{session_id}/messages", "Send message to AI concierge and receive response.", ["Chat conversation"])


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


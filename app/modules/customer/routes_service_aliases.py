"""Top-level aliases for the mobile app's separated service feeds.

The canonical routes remain under ``/customer``. These aliases expose the
same handlers at ``/restaurants``, ``/hotels``, and ``/spas`` so clients can
consume each service as an independent API surface.
"""

from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.modules.customer.router import router as customer_router

router = APIRouter()
_service_prefixes = ("/customer/restaurants", "/customer/hotels", "/customer/spas")

for route in customer_router.routes:
    if not isinstance(route, APIRoute) or not any(route.path.startswith(prefix) for prefix in _service_prefixes):
        continue
    alias_path = route.path.removeprefix("/customer")
    router.add_api_route(
        alias_path,
        route.endpoint,
        methods=list(route.methods or []),
        response_model=route.response_model,
        status_code=route.status_code,
        response_class=route.response_class,
        tags=route.tags,
        summary=route.summary,
        description=route.description,
        deprecated=route.deprecated,
        operation_id=f"service_alias_{route.name}",
    )

"""Compatibility shim for older imports.

This module now re-exports the async v1 auth router so there is only one
implementation of customer auth endpoints.
"""

from app.api.v1.routers.auth import router

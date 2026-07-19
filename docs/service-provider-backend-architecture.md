# Service-provider and backend architecture

## Scope and source of truth

The FastAPI OpenAPI document is the API contract. The service-provider app must call the backend through its Next.js `/api` proxy, never directly from the browser. The proxy owns access-token cookies, one refresh retry, request timeouts, and safe error responses.

```text
Browser UI
  -> Next.js API proxy (same-origin auth boundary)
    -> FastAPI /api/v1/vendor endpoints
      -> vendor service/repository layer
        -> MongoDB + Cloudinary
```

Platform-owned data and vendor-owned data must remain separate:

| Data | Owner | Provider access |
| --- | --- | --- |
| Global/category commission | Platform admin | Read only |
| Platform legal terms | Platform admin | Read public version |
| Provider legal additions | Provider | Read/write own vendor-scoped copy |
| Profile, services, rooms, promotions | Provider | Read/write own records |
| Customer account data | Customer/platform | Read only safe fields when a booking relationship exists |

## Contract rules

1. Every frontend method/path pair must exist in FastAPI. `tests/test_vendor_endpoint_contract.py` enforces the current inventory.
2. Export `app.openapi()` in CI and generate TypeScript request/response types from it. Treat removed paths, fields, or status codes as breaking changes.
3. Use one response convention:
   - Single resource: `{ "data": { ... } }`
   - Collection: `{ "items": [...], "page": 1, "page_size": 25, "total": 120 }`
   - Error: `{ "code": "stable_machine_code", "message": "safe user message", "request_id": "...", "fields": {} }`
4. Use cursor pagination for notifications and large booking/customer collections; offset pagination is acceptable for small admin tables.
5. Use ISO-8601 UTC timestamps at the API boundary and explicit `start_date`/`end_date` query parameters for reporting.
6. POST creates, PATCH partially updates, PUT fully replaces, and DELETE is idempotent. Partial-update schemas must make all patchable fields optional and reject an empty payload.

## Frontend state model

TanStack Query owns server state. Local component state is limited to open dialogs, form drafts, selected rows, and other temporary UI state.

- Dashboard/analytics: stale after 30 seconds; refetch on focus and reconnect.
- Bookings/notifications: stale after 10–15 seconds; poll only while the page is visible until server events are introduced.
- Profile/settings/services: stale after 5 minutes; invalidate the exact resource key after a successful mutation.
- Mutations: disable duplicate submission, show field errors for 422 responses, and use optimistic updates only for reversible actions such as notification read state.
- Abort fetches on navigation and enforce a 15-second proxy timeout.
- Do not copy query results into long-lived local state. Derive filtered and sorted rows with memoized selectors.

Recommended query-key shape:

```text
['vendor', vendorId, 'dashboard', range]
['vendor', vendorId, 'bookings', filters, page]
['vendor', vendorId, 'services', category]
['vendor', vendorId, 'settings', section]
```

## Backend structure

Target one asynchronous data-access path rather than mixing sync PyMongo and Motor:

```text
router (HTTP validation/auth)
  -> application service (authorization + use case)
    -> repository interface (vendor-scoped queries)
      -> Motor implementation
```

- Pass a typed vendor identity into every provider use case.
- Put `vendor_id` in every provider-owned query and compound index.
- Keep index creation in deployment migrations, never repository constructors or request handlers.
- Move booking-side effects—notifications, loyalty points, availability, receipts—behind an application service and transaction/outbox boundary.
- Use an outbox worker for email, push notifications, analytics aggregation, and Cloudinary cleanup so the API request is not blocked by third-party latency.
- Store asset metadata only after upload succeeds; clean orphaned uploads asynchronously.
- Generate durable PDF receipts in object storage for production. The current printable HTML response is the safe synchronous fallback.

## Security and reliability

- Keep provider authentication in HttpOnly, Secure, SameSite cookies at the Next.js boundary.
- Validate ownership in the database query itself (`_id` plus `vendor_id`) to prevent IDOR vulnerabilities.
- Never return raw user or vendor MongoDB documents. Response DTOs must explicitly allow-list fields.
- Rate-limit login, password reset, OTP, uploads, review replies, and support messages.
- Validate upload MIME type, file signature, size, and image dimensions; scan documents before making them available.
- Use request IDs across Next.js and FastAPI. Log route, status, duration, vendor ID, and request ID, but never tokens, passwords, OTPs, or full customer PII.
- Track p50/p95/p99 latency, error rate, MongoDB query duration, refresh failures, and third-party upload time.

Suggested service levels:

| Operation | p95 target |
| --- | ---: |
| Dashboard cached read | 400 ms |
| Booking list/detail | 500 ms |
| Normal mutation | 700 ms |
| Upload/receipt job acceptance | 1 s |

## Rollout order

1. Deploy backend contract and database indexes.
2. Run backend smoke checks for login, dashboard, asset registration, promotion patch, settings, customer detail, and receipt generation.
3. Deploy the service-provider app.
4. Watch request IDs, 401 refresh loops, 422 responses, p95 latency, and error rate for at least one normal traffic cycle.
5. Generate the TypeScript client from OpenAPI and migrate remaining `Record<string, unknown>` calls feature by feature.
6. Consolidate repositories on Motor, then introduce the outbox worker and event-driven notifications.

Do not deploy the frontend asset-registration change before the backend `/vendor/menu-services/assets` endpoint is live.

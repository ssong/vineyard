Design as an API-only product. The "design" output focuses on:

- API surface (versioned routers under `app/api/v1/`)
- Request/response shapes
- Auth model (which endpoints require what)
- Integration patterns clients will use

User flows should describe **API client** flows (e.g., "client obtains token → calls POST /resources → polls GET /resources/{id}") rather than UI flows.

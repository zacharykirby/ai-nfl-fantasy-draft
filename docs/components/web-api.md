# Private Web API and Mobile Preview

The first web milestone exposes a read-only FastAPI adapter over the existing board,
session, and deterministic recommendation services. It also serves a narrow,
phone-first cockpit page from the same process.

## Start locally

Install the project in editable mode, then run:

```bash
draft-server
```

Open `http://127.0.0.1:8000`. Use `?session=NAME` to choose a saved session.

The server binds to localhost by default. Tailscale Serve deployment is intentionally
deferred until the state-changing routes and confirmation UI are complete.

## Read-only contract

```text
GET /api/v1/health
GET /api/v1/board/summary
GET /api/v1/sessions
GET /api/v1/sessions/{name}
GET /api/v1/sessions/{name}/cockpit
GET /api/v1/sessions/{name}/players/search?q=...
GET /api/v1/sessions/{name}/available?position=RB&limit=20
GET /api/v1/sessions/{name}/recommendation?mode=balanced
```

The OpenAPI document is available at `/openapi.json` and interactive documentation at
`/docs`.

## Boundaries

- Route handlers compose existing domain services; they do not rank players.
- Session names are restricted to safe filename slugs inside the configured directory.
- Session detail responses omit the embedded full board snapshot.
- API responses disable caching and include basic private-app security headers.
- Filesystem paths and secrets are not returned to the browser.
- The API currently contains no POST, PUT, PATCH, or DELETE operations.

## Cockpit response

`DraftCockpitService` combines current pick context, user roster, recent selections,
recommendation, best available players, per-position availability, tier alerts,
position-run state, and local health into one presentation read model. The CLI domain
objects remain authoritative.

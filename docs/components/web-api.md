# Private Web API and Mobile Preview

The web application exposes a FastAPI adapter over the existing board, session, and
deterministic recommendation services. It also serves a narrow, phone-first cockpit
page from the same process.

## Start locally

Install the project in editable mode, then run:

```bash
draft-server
```

Open `http://127.0.0.1:8000`. Use `?session=NAME` to choose a saved session.

The server binds to localhost by default. Tailscale Serve deployment is intentionally
deferred until the state-changing routes and confirmation UI are complete.

## HTTP contract

```text
GET /api/v1/health
GET /api/v1/board/summary
GET /api/v1/sessions
GET /api/v1/sessions/{name}
GET /api/v1/sessions/{name}/cockpit
GET /api/v1/sessions/{name}/players/search?q=...
GET /api/v1/sessions/{name}/available?position=RB&limit=20
GET /api/v1/sessions/{name}/recommendation?mode=balanced
POST /api/v1/sessions/{name}/commands/interpret
POST /api/v1/sessions/{name}/picks
POST /api/v1/sessions/{name}/picks/bulk/preview
POST /api/v1/sessions/{name}/picks/bulk
POST /api/v1/sessions/{name}/undo
```

The OpenAPI document is available at `/openapi.json` and interactive documentation at
`/docs`.

## Boundaries

- Route handlers compose existing domain services; they do not rank players.
- Session names are restricted to safe filename slugs inside the configured directory.
- Session detail responses omit the embedded full board snapshot.
- API responses disable caching and include basic private-app security headers.
- Filesystem paths and secrets are not returned to the browser.
- Natural-language pick phrases are interpreted without changing state.
- Pick recording requires a second explicit request after user confirmation.
- State mutations are serialized per session and accept idempotency request IDs.
- Undo can require the exact latest event ID shown in its confirmation sheet.
- Bulk catch-up validates the starting pick and saves the complete batch atomically.
- Successful mutations return the refreshed cockpit snapshot.
- Model-backed assistant questions remain read-only and are not connected to the web
  composer yet.

## Cockpit response

`DraftCockpitService` combines current pick context, user roster, recent selections,
recommendation, best available players, per-position availability, tier alerts,
position-run state, and local health into one presentation read model. The CLI domain
objects remain authoritative.

## Text composer

The mobile composer recognizes conservative selection statements including `someone
got Gibbs`, `Gibbs picked`, `they took Chase`, and `draft Puka Nacua`. Unique surnames
resolve through the session's available-player matcher. Ambiguous or unavailable
players produce structured errors and do not advance the draft.

The confirmation dialog displays the resolved full player name, overall pick, and
team. Only confirmation calls the pick mutation endpoint.

## Undo and catch-up

**Undo last** confirms the exact active selection before restoring it to the pool. A
stale confirmation cannot reverse a newer selection. **Catch up** accepts 2–20 names
separated by commas, semicolons, or new lines. Preview resolves each name against the
evolving available pool and assigns its pick and snake-draft team. Commit verifies
that the draft still starts at the previewed pick and writes the full batch once.

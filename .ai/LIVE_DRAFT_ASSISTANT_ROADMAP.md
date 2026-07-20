# Live Fantasy Draft Cockpit Roadmap

**Status:** Active product and implementation plan

**Product direction:** Private, mobile-first draft cockpit hosted on the user's PC

**Last updated:** 2026-07-19

## 1. Product Vision

Turn this repository into the analytical engine and private server for a fast,
phone-friendly fantasy football draft assistant.

The repository remains responsible for the difficult and trustworthy work:

1. Build current player projections from attributable sources.
2. Blend projections with historical performance, availability, news, risk, and ADP.
3. Produce auditable position rankings, tiers, and VORP-based priorities.
4. Track the complete live draft and every team's roster.
5. Generate deterministic recommendations that remain useful without a model.
6. Give an optional OpenRouter model a small, validated evidence packet so it can
   explain tradeoffs and answer questions without inventing draft facts.

The primary user experience becomes a responsive web application running on the
user's PC and accessed from a phone over Tailscale. It should feel like a draft
cockpit, not a desktop dashboard squeezed onto a small screen and not a generic chat
window that requires constant typing.

The core draft-night loop is:

```text
See the current pick and best available players
                  |
Record a selection with one or two taps
                  |
Watch availability, tiers, runs, and recommendations update immediately
                  |
Ask a short question only when judgment or explanation is useful
```

## 2. Product Decisions

These decisions supersede the earlier plan to treat the CLI as the final primary
interface or to expose a public API for a Custom GPT.

### Private hosting

- The application server runs on the user's PC.
- The backend listens on localhost by default.
- Tailscale Serve provides private HTTPS access to the phone through the user's
  tailnet.
- Tailscale Funnel and public inbound access are out of scope.
- The phone never receives the OpenRouter API key.
- OpenRouter calls originate from the PC and are outbound-only.

### Mobile-first interaction

- The primary interface is optimized first for a narrow portrait phone viewport.
- Recording a normal pick should require no more than two deliberate taps.
- Drafting the recommended player must still require explicit confirmation.
- Search, recommendation, undo, and position filters remain reachable with one hand.
- Important information appears above the fold; secondary evidence opens on demand.
- The terminal CLI remains a supported fallback and debugging interface.

### Deterministic core, optional model

- Draft facts and state are always owned by local deterministic code.
- The model explains and compares; it does not calculate availability or mutate state.
- Every model-named player must be in the supplied available candidate allowlist.
- If OpenRouter is slow, unavailable, or returns malformed output, the UI immediately
  shows deterministic advice.
- A user must be able to finish the entire draft with no model connection.

### One backend, multiple clients

- The web UI and CLI use the same session and recommendation services.
- HTTP route handlers stay thin and contain no ranking or draft strategy logic.
- Existing modules are wrapped before they are reorganized.
- Stable versioned JSON contracts separate the domain layer from the interface.

## 3. Target Architecture

```text
                         PRE-DRAFT / OCCASIONAL

 Historical stats   Projections   ADP   News/risk   Player identity
        \               |          |       |              /
                         Data pipeline
                              |
                 outputs/player_rankings.json
                              |
                   outputs/draft_board.json
                              |
                      Board validation


                              DRAFT NIGHT

 Phone browser
      |
      | Private HTTPS inside tailnet
      v
 Tailscale Serve on PC
      |
      | Reverse proxy to localhost only
      v
 FastAPI application
      |
      +-- Static mobile frontend
      +-- Versioned JSON API
      +-- Draft session service ------> sessions/*.json
      +-- Recommendation engine
      +-- Assistant context builder
      |
      +-- Optional outbound request --> OpenRouter

 CLI ----------------------------------------------------+
      uses the same board, session, and recommendation domain code
```

### Initial technology choices

Backend:

- Python 3.12
- FastAPI for HTTP routing, validation, and generated API documentation
- Existing JSON session persistence for the first release
- Existing OpenRouter client and deterministic fallback

Frontend:

- Semantic HTML, modern CSS, and small JavaScript modules
- Served by the same FastAPI process
- No required Node build toolchain for the first release
- Progressive enhancement toward an installable PWA after the core flow is proven

This is a deliberate reliability choice. The first mobile interface does not need a
large frontend framework. If later UI complexity demonstrates a real need, the API
boundary allows a React, Vue, or other client without rewriting the domain engine.

## 4. Existing Foundation

The following capabilities are implemented and should be reused rather than rebuilt.

### Data and board

- Season-aware historical data ingestion
- Current-season projection acquisition and import
- Projection provenance and validation
- Player identity normalization and conflict reporting
- VORP-based ranking with auditable score components
- Versioned `outputs/player_rankings.json`
- Position-first `outputs/draft_board.json`
- Independent QB, RB, WR, and TE priorities
- Board health checks and readiness status

### Draft state

- Versioned draft-session JSON contract
- Immutable board snapshot per session
- Snake-order pick ownership
- Every-team roster tracking
- Exact, prefix, and conservative fuzzy player matching
- Duplicate and unavailable-player prevention
- Atomic autosave after mutations
- Event-backed selection and undo history
- Crash-safe session resume

### Recommendations and assistant

- Safe, balanced, and upside recommendation modes
- Board value, position value, VORP, roster need, tier scarcity, and risk signals
- Recent position-run detection
- ADP-based survival estimate to the user's next pick
- Bounded model context and candidate allowlist
- Structured model response validation
- Deterministic fallback on timeout, connection failure, or invalid model output

### Existing interface

- Noninteractive draft session commands
- Interactive terminal dashboard
- Human-readable and JSON recommendation output
- Read-only conversational questions

The CLI remains the recovery path throughout web development. A web feature is not
complete if it can corrupt or diverge from the session behavior already tested by the
CLI.

## 5. Domain and API Contracts

The browser should never read or write session files directly. It communicates with
the application through a small versioned API.

### Draft cockpit snapshot

The primary read model should let the phone render the whole above-the-fold screen
with one request:

```json
{
  "schema_version": "1.0",
  "session": {
    "id": "home-league",
    "round": 4,
    "current_pick": 34,
    "current_team": 4,
    "user_team": 5,
    "next_user_pick": 36,
    "picks_until_user": 2
  },
  "user_roster": [],
  "recent_picks": [],
  "recommendation": {},
  "best_available": [],
  "top_available_by_position": {},
  "tier_alerts": [],
  "position_run": {},
  "health": {
    "board": "ready",
    "model": "online",
    "autosave": "ok"
  }
}
```

This response is composed from existing domain services. It is a presentation read
model, not a second recommendation engine.

### Initial endpoints

```text
GET    /api/v1/health
GET    /api/v1/board/summary
GET    /api/v1/sessions
POST   /api/v1/sessions
GET    /api/v1/sessions/{session_id}
GET    /api/v1/sessions/{session_id}/cockpit
GET    /api/v1/sessions/{session_id}/players/search?q=...
GET    /api/v1/sessions/{session_id}/available?position=RB&limit=20
GET    /api/v1/sessions/{session_id}/recommendation?mode=balanced
POST   /api/v1/sessions/{session_id}/picks
POST   /api/v1/sessions/{session_id}/picks/bulk
POST   /api/v1/sessions/{session_id}/undo
POST   /api/v1/sessions/{session_id}/assistant
```

### Mutation rules

- Every state-changing request requires an explicit endpoint and valid payload.
- Assistant messages are always read-only.
- A successful mutation returns the new cockpit snapshot so the UI updates without a
  second round trip.
- Ambiguous names return a structured conflict with candidate choices.
- Duplicate submissions are safe to retry or rejected without advancing the draft.
- The backend serializes session mutations to prevent two rapid taps from corrupting
  the event log.
- Undo returns exactly which selection was reversed.
- Bulk entry is atomic by default: either the entire ordered batch is valid or none of
  it is applied.

### Error contract

Errors should be actionable on a phone:

```json
{
  "error": {
    "code": "ambiguous_player",
    "message": "Multiple players match Williams.",
    "recoverable": true,
    "candidates": []
  }
}
```

Do not expose stack traces, environment values, API keys, or raw provider responses to
the browser.

## 6. Mobile Experience

### Primary cockpit screen

The default screen answers five questions without scrolling:

1. Whose pick is it?
2. How long until my pick?
3. Who is recommended right now?
4. Which alternatives or tier cliffs matter?
5. How do I record the player who was just selected?

Suggested portrait layout:

```text
+--------------------------------+
| R4 · Pick 34       You in 2     |
| Board ready · Model online      |
+--------------------------------+
| RECOMMENDATION                  |
| Puka Nacua · WR1 · Tier 1       |
| 94.1 VORP · unlikely to survive |
| [ Draft Puka ]  [ Why? ]        |
+--------------------------------+
| Alternatives                    |
| Saquon Barkley       [ Draft ]  |
| CeeDee Lamb          [ Draft ]  |
+--------------------------------+
| [All] [RB] [WR] [QB] [TE]       |
| Search a selected player...     |
+--------------------------------+
| Recent: Gibbs · Bijan · Chase   |
+--------------------------------+
| Board   Roster   Ask   Undo      |
+--------------------------------+
```

### Interaction requirements

- Minimum comfortable touch targets of roughly 44 CSS pixels.
- No horizontal scrolling in the primary flow.
- Sticky pick/search controls where they materially reduce thumb travel.
- Search results show player, position, team, tier, and availability.
- Selecting a player opens a compact confirmation sheet rather than immediately
  mutating state.
- Confirmation clearly names the player, overall pick, and drafting team.
- The just-recorded player disappears immediately from every availability view.
- Undo is prominent but requires confirmation showing the exact pick being reversed.
- Filters and scroll position survive ordinary screen refreshes where practical.
- Color is supportive, never the only way status or risk is communicated.
- Core actions remain usable with the model offline.

### Views

#### Cockpit

- Current round, overall pick, current team, and countdown to user pick
- Primary recommendation and concise reason
- Two or three alternatives
- Tier-drop and position-run alerts
- Quick selection search
- Recent selections
- Connectivity, board-health, and autosave status

#### Board

- All, QB, RB, WR, and TE filters
- Available players by default
- Tier boundaries visually separated
- Compact rows with rank, ADP, projection, VORP, team, and risk indicators
- Expandable evidence rather than dense always-visible columns
- Fast draft action on each available player

#### My roster

- Players grouped by projected roster slot
- Starter needs and FLEX eligibility
- Bye-week concentration shown as a secondary warning
- Current construction summary such as `RB 2 · WR 1 · QB 0 · TE 0`

#### Draft log

- Ordered selections with pick, round, team, player, and position
- Search and team filtering
- Undo latest pick in the first release
- Arbitrary historical correction only after event replay semantics are designed and
  tested

#### Ask

- Short prompt field with phone dictation support
- Suggested prompts such as `Can I wait at QB?` and `Compare these two players`
- Compact answer with recommendation, alternatives, confidence, evidence, and cautions
- No chat-driven state mutation

### Voice strategy

The first release relies on the phone keyboard's speech-to-text. Dedicated audio
recording, transcription, wake words, and speech playback are deferred until normal
dictation is tested during simulations. Voice convenience must not complicate the
critical state path.

## 7. Security and Privacy Model

### Network boundary

- FastAPI binds to `127.0.0.1` by default.
- Tailscale Serve terminates private HTTPS and proxies to the local port.
- The application is not configured with Tailscale Funnel.
- No router port forwarding, public DNS record, public tunnel, or public cloud ingress
  is required.
- Tailnet access controls determine which devices or users can reach the service.

### Secrets

- `.env` remains server-side and untracked.
- `OPENROUTER_API_KEY` is never included in HTML, JavaScript, API responses, logs, or
  session files.
- The frontend never calls OpenRouter directly.
- Error messages redact upstream response details that might contain sensitive data.
- `.env.example` documents names and safe placeholders only.

### Browser/API defenses

- Restrict allowed hosts and origins to the local and expected tailnet addresses.
- State-changing routes use POST and reject cross-origin requests.
- Do not trust client-supplied pick number, team ownership, or player availability;
  recompute them from the loaded session.
- Validate every request and response at the HTTP boundary.
- Add security headers suitable for a same-origin private web application.
- Treat Tailscale as the access boundary, while still keeping safe application-level
  validation and optional identity-header checks.

## 8. Reliability and Performance Budgets

Draft-night speed matters more than visual novelty.

### Target budgets

- Cockpit load from local server: under 500 ms on a healthy tailnet connection
- Search response: under 200 ms for local data
- Pick or undo mutation including autosave: under 500 ms
- Deterministic recommendation: under 500 ms
- Model response target: under 5 seconds
- Model timeout: short enough to fall back before advice becomes useless

These are initial engineering targets, not guarantees. Measure them in realistic phone
simulations and optimize the slowest critical path.

### Failure behavior

| Failure | Required behavior |
| --- | --- |
| OpenRouter unavailable | Show deterministic advice and keep every state action working |
| Internet unavailable | Keep local/tailnet application working if the phone can still reach the PC |
| Browser refresh | Reload the exact saved session state |
| Double tap or retry | Never record the same pick twice |
| Ambiguous player | Show candidates and make no state change |
| Invalid board | Refuse to create a live session and show health issues |
| PC process restart | Resume from the atomically saved session |
| Phone disconnect | Preserve server state; reconnect and refresh safely |
| Corrupt session file | Fail closed and preserve the file for diagnosis |

### Emergency fallback

Before draft night, generate a small static markdown or printable board containing:

- Data freshness and health warnings
- Overall priorities
- Tier-aware QB, RB, WR, and TE lists
- Key strategy notes
- Startup and recovery commands

This artifact is not live state. It is the emergency cheatsheet if the PC or phone
workflow becomes unavailable.

## 9. Implementation Plan

### Milestone 0 — Freeze and verify the foundation

**Status: Mostly complete; verify before web work.**

Deliverables:

- Run the existing board, session, recommendation, assistant, and terminal tests.
- Regenerate and validate the current board.
- Record current health warnings as known input limitations.
- Confirm `.env` and session files are excluded from version control.
- Add a full-draft CLI simulation fixture if one is not already present.
- Document which existing functions are the supported domain-service entry points.

Exit criteria:

- Board health is `ready`.
- Existing tests pass without web dependencies.
- A complete draft can still be conducted and recovered through the CLI.

### Milestone 1 — Application service and read-only API

**Status: Implemented.**

Deliverables:

- Add FastAPI and an application entry point.
- Add typed request/response schemas with an API version prefix.
- Add health, board summary, session list, session detail, cockpit, player search,
  availability, and deterministic recommendation endpoints.
- Compose cockpit responses from existing domain services.
- Serve a minimal static page from the same process.
- Add API tests using temporary boards and sessions.
- Keep route handlers free of draft logic.

Delivered:

- Packaged `src/fantasy_draft` runtime with compatibility CLI wrappers
- `DraftCockpitService` presentation read model
- Versioned health, board, session, cockpit, search, availability, and recommendation reads
- Typed response contracts and structured public errors
- Same-process static mobile frontend
- Read-only API and domain parity tests
- Local `draft-server` entry point bound to localhost by default

Exit criteria:

- Read-only API responses match CLI/domain results for the same fixtures.
- No endpoint leaks secrets or filesystem implementation details.
- The generated API schema accurately describes the supported routes.

### Milestone 2 — Safe web mutations

**Status: In progress. The safe mutation core and mobile controls are implemented;
browser session creation/resume remains.**

Deliverables:

- Create and resume sessions from the browser.
- Add pick, bulk-pick, and undo endpoints.
- Add structured ambiguous-name and unavailable-player responses.
- Serialize mutations per session.
- Return the refreshed cockpit snapshot after successful mutations.
- Add tests for retries, rapid duplicate submissions, ambiguity, invalid order, undo,
  autosave, and restart recovery.

Delivered so far:

- Conservative natural-language pick interpretation without mutation
- Unique-surname matching with explicit ambiguity handling
- Full player, pick, and team confirmation before recording
- Per-session in-process mutation serialization
- Idempotent pick and undo application services
- Pick and undo HTTP endpoints returning fresh cockpit snapshots
- Fixed mobile text composer and selection confirmation dialog
- Exact-event undo confirmation with stale-state rejection
- Atomic 2–20 player catch-up preview and commit
- Persisted idempotency across service restarts
- Retry, concurrent double-tap, rollback, interpretation, API, and domain tests

Exit criteria:

- Browser and CLI produce equivalent session event histories.
- Rapid repeated taps cannot duplicate or skip a pick.
- All failed mutations leave the session unchanged.

### Milestone 3 — Mobile cockpit MVP

Deliverables:

- Build the responsive cockpit screen.
- Add player search and explicit draft confirmation sheet.
- Add best-available position filters.
- Add recommendation and alternative cards.
- Add recent picks, compact roster summary, and tier/run alerts.
- Add undo confirmation and clear success/error feedback.
- Add visible board, model, autosave, and connectivity status.
- Test common phone widths and landscape recovery.

Exit criteria:

- A simulated draft can be entered entirely from a phone without a physical keyboard.
- Normal pick entry requires no more than two deliberate taps after locating a player.
- The most important state fits within one portrait screen with no horizontal scroll.
- Refresh, reconnect, and accidental double taps do not corrupt state.

### Milestone 4 — Board, roster, and draft-log views

Deliverables:

- Add tier-aware position board with available-only default.
- Add player evidence details on demand.
- Add user roster with needs and bye-week summary.
- Add complete draft log and team filters.
- Add desktop-responsive enhancements without weakening the phone layout.
- Decide whether limited polling, server-sent events, or manual refresh best fits the
  single-user local deployment; avoid real-time infrastructure without a measured need.

Exit criteria:

- Every important CLI read operation has an equivalent mobile view.
- Position and tier context is understandable without opening raw JSON.
- The interface stays responsive with the full configured board and draft log.

### Milestone 5 — Conversational assistant in the cockpit

Deliverables:

- Connect the existing assistant context builder and response validator to the API.
- Add the Ask view and suggested prompts.
- Display source mode: model or deterministic fallback.
- Keep model calls cancellable or ignorable by the UI.
- Add latency measurement and a strict server-side timeout.
- Test unavailable-player hallucinations, malformed responses, upstream errors, and
  concurrent state changes while an answer is in flight.

Exit criteria:

- The assistant never mutates state.
- Every recommended player is still available when the response is displayed, or the
  UI marks the answer stale and refreshes advice.
- Model failure never blocks recording picks or viewing deterministic recommendations.

### Milestone 6 — Private Tailscale deployment

Deliverables:

- Add documented localhost startup command.
- Add Tailscale Serve setup and status checks.
- Add a single draft-night startup script or command that validates the board, starts
  the app, and prints the private URL.
- Document how to stop Serve and the application.
- Add PC sleep/power guidance and phone reconnection steps.
- Verify the service is unreachable from a non-tailnet device.
- Verify no Funnel configuration is active.

Exit criteria:

- The phone can complete a simulated draft over cellular while connected to Tailscale.
- The backend remains bound to localhost.
- The OpenRouter key is absent from browser traffic and built assets.
- Startup and recovery can be performed from a short runbook.

### Milestone 7 — Draft simulation and hardening

Simulation matrix:

- 8-, 10-, and 12-team leagues
- Standard, half-PPR, and PPR
- Early, middle, and late draft positions
- FLEX and Superflex configurations
- Position runs and unexpected reaches
- Major ADP fallers
- Ambiguous search terms and misspellings
- Bulk catch-up after several missed picks
- Double taps and delayed network responses
- Undo, browser refresh, server restart, and phone reconnect
- OpenRouter timeout, invalid response, and total internet loss
- Stale, incomplete, and not-ready boards

Evaluate:

- Time required to record each pick
- Recommendation and search latency
- Recovery time after an incorrect entry
- Missed or duplicated selection rate
- Visibility of tier cliffs and roster needs
- Model token usage, latency, and cost
- Battery and readability during a complete phone session

Exit criteria:

- At least three complete phone-based simulated drafts finish without state corruption.
- Critical paths have regression tests.
- Known failures produce short, actionable messages.
- The user can recover from a wrong pick in seconds.

### Milestone 8 — PWA and quality-of-life improvements

Only pursue after the mobile MVP survives realistic drafts.

Candidates:

- Installable home-screen PWA shell
- Cached application shell and emergency read-only board
- Wake-lock request during an active draft
- Better bulk pick entry
- Arbitrary historical correction with safe event replay
- Larger desktop board mode
- Haptics where browser support permits and the feedback is useful
- Optional speech transcription or spoken answers
- Draft result export and post-draft roster analysis

Do not cache mutable draft state in a way that competes with the server's authoritative
session. Offline mutation and later synchronization are explicitly out of scope until
there is a proven need and a conflict-safe design.

## 10. Testing Strategy

### Domain tests

Continue testing ranking, board, session, recommendation, and assistant modules without
starting an HTTP server. Domain correctness should not depend on FastAPI or a browser.

### API tests

- Contract shape and versioning
- HTTP status and structured error mapping
- Read parity with domain services
- Mutation atomicity and idempotency behavior
- Per-session mutation serialization
- Secret and internal-path leakage checks

### Browser tests

- Primary flow at representative small-phone widths
- Touch confirmation and undo behavior
- No horizontal overflow
- Search, filters, and stale-result handling
- Reload and reconnect behavior
- Model-online and model-offline states
- Basic accessibility: labels, focus, contrast, and keyboard operation

Start with focused browser-level smoke tests for critical paths. Add broader end-to-end
coverage after the UI structure stabilizes.

### Manual draft-night rehearsal

Use the actual phone, cellular data, Tailscale, target PC, and OpenRouter configuration.
A desktop browser resized to mobile width is useful during development but is not an
adequate final test.

## 11. Observability and Operations

The application should expose enough local information to diagnose problems without
turning into an operations project.

- Structured local logs with timestamps, request IDs, route, latency, and outcome
- No API keys, full prompts, or sensitive environment values in logs
- Visible last autosave time and path in the server/CLI output
- Visible board generation time and health in the cockpit
- Model source, model slug, latency, fallback reason, and token usage when available
- Lightweight `/health` response for local startup checks
- Optional bounded log file rotation before draft night

## 12. Immediate Next Work

The next implementation session should proceed in this order:

1. Connect question-classified composer text to the existing read-only assistant.
2. Add browser session creation, selection, and resume controls.
3. Test delayed responses and real phone double taps against the running server.
4. Add process-level file locking only if multiple server workers become supported.
5. Add the full position board, roster detail, and draft-log views.

The next visible demo should support safe undo from the phone and conversational
questions in the same composer without allowing the model to mutate state.

## 13. Known Risks and Constraints

- The PC is a single point of service; sleep, restart, or power loss interrupts phone
  access until it recovers.
- Tailscale access does not replace application validation or safe mutation design.
- Mobile browsers may suspend background tabs; the UI must refresh state on focus.
- Draft platform selections remain manual unless a later stable integration is added.
- Missing bye weeks, teams, or ADP-derived projections must remain visible as data
  warnings rather than being hidden by the UI.
- Historical and projection sources can change format and break preseason refreshes.
- OpenRouter model behavior, latency, and model availability can change; deterministic
  fallback remains mandatory.
- Arbitrary correction of an older pick is more complex than undoing the latest event
  and must not be implemented as unsafe JSON editing.
- A large frontend framework could slow delivery and add build/runtime failure modes
  before the interaction design is proven.

## 14. Definition of Draft-Night Ready

The product is ready for a real draft when:

- The current board is attributable, reviewed, and reports `health.status = ready`.
- The PC starts the backend with one documented command and binds only to localhost.
- Tailscale Serve exposes the site only inside the intended tailnet.
- The phone can create or resume a session and record a complete simulated draft.
- The cockpit clearly shows current pick, time-to-user-pick context, recommendation,
  alternatives, tier alerts, recent picks, roster, and health.
- Search and normal pick entry are fast enough for live use.
- Duplicate, ambiguous, or unavailable selections never corrupt state.
- Undo, autosave, refresh, reconnect, and server restart recovery are tested.
- Deterministic recommendations remain fully usable without OpenRouter.
- The model cannot mutate state or recommend unavailable players without rejection.
- Secrets never reach browser code, responses, session files, or logs.
- At least three full phone-based draft simulations pass.
- A short runbook covers startup, Tailscale verification, recovery, shutdown, and the
  emergency static cheatsheet.

## 15. Deferred Ideas

These may be valuable later but are not part of the first private mobile release:

- Public hosting or public Custom GPT Actions
- Tailscale Funnel
- Native iOS or Android applications
- Automatic scraping of a third-party live draft room through browser automation
- Multi-user simultaneous draft-room collaboration
- Cloud database or account system
- Offline write synchronization
- Dedicated realtime voice conversation
- Push notifications
- Platform-specific league and draft integrations
- Public distribution or multi-tenant hosting

The near-term goal is narrower and more useful: one user, one phone, one trusted PC,
one private tailnet, and a draft assistant fast and reliable enough to use on the
clock.

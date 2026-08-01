# Casual Co-pilot Design Baseline

This design uses the 2026-08-01 audit as its baseline. It preserves the current event-backed draft engine, mutation contracts, and deterministic analytical pipeline. Only Patch 1 is authorized for implementation in this phase.

## 1. Proposed cockpit wireframe

```text
┌────────────────────────────────────────────┐
│ LIVE DRAFT       home-league    Drafts  ↻ │
│ Half-PPR · Board Jul 21 · 2 warnings      │
├──────────┬──────────┬──────────┬──────────┤
│ Round 4  │ Pick 31  │ On T7    │ You in 2 │
├─────────────────────┬──────────────────────┤
│ Undo last           │ Catch up             │
├────────────────────────────────────────────┤
│ Search / record a player                   │
│ [ Player name…                    Record ] │
├────────────────────────────────────────────┤
│                                            │
│            [ !!!  OH GOD  !!! ]            │
│       One tap; no typing; no mutation      │
│                                            │
│ ┌ situational card, hidden until tapped ┐  │
│ │ THE RUN LOOKS SCARIER THAN IT IS      │  │
│ │ Urgency: MEDIUM                       │  │
│ │ Lean / Safe build / Upside swing      │  │
│ │ Two-sentence explanation + caveats    │  │
│ │ Can wait: Probably                    │  │
│ │ [Can I wait?] [Why not…] [Upside]     │  │
│ └───────────────────────────────────────┘  │
├────────────────────────────────────────────┤
│ My roster (compact)       Recent picks     │
├────────────────────────────────────────────┤
│ ▸ Talk shop (closed by default)            │
├────────────────────────────────────────────┤
│ Board ✓  Autosave ✓  Connection ✓          │
└────────────────────────────────────────────┘
```

The OH GOD button is visually prominent but does not resemble a mutation control. Pick recording and Undo retain their current confirmation semantics. Chill mode hides persistent recommendations. Full assistant mode may expose one compact deterministic recommendation only on the user's turn; external interpretation always requires a tap.

## 2. Exact OH GOD structured response schema

Proposed API schema version: `oh_god.v1`.

```json
{
  "schema_version": "oh_god.v1",
  "headline": "string, 1-80 characters",
  "urgency": "low | medium | high",
  "situation_type": "value_fall | tier_cliff | position_run | roster_pressure | normal_board | data_uncertain | mixed",
  "explanation": "string, 1-320 characters",
  "primary_option": {
    "player_id": "available allowlisted ID",
    "label": "Model/data lean",
    "reason": "string, 1-140 characters"
  },
  "safe_option": {
    "player_id": "available allowlisted ID",
    "label": "Safer build",
    "reason": "string, 1-140 characters"
  },
  "upside_option": {
    "player_id": "available allowlisted ID",
    "label": "Upside swing",
    "reason": "string, 1-140 characters"
  },
  "can_wait": "yes | probably | risky | no | unknown",
  "can_wait_reason": "string, 1-180 characters",
  "caveats": ["0-3 strings, each at most 140 characters"],
  "evidence_summary": {
    "candidate_score_gap": "number or null",
    "close_call": "boolean",
    "tier_cliffs": ["position strings"],
    "recent_run_positions": ["position strings"],
    "data_warning_count": "nonnegative integer",
    "forecast_freshness": "fresh | warning | stale | unknown"
  },
  "draft_revision": "exact session revision used for generation"
}
```

Validation rules:

- All three player IDs must be distinct, currently available, and present in the supplied allowlist. If fewer than three credible distinct choices exist, an option may be `null`; no outside player may be substituted.
- `draft_revision` must equal the revision supplied in context. The server reloads the session after inference and marks the envelope stale if the revision or current pick changed, or if any option is no longer available.
- Headline, explanation, reasons, and caveats are length-bounded. The model may not add fields or include hidden reasoning.
- `close_call` is deterministic. The model cannot claim a decisive lean when the deterministic score gap is inside the configured close-score threshold.
- Missing/stale data must appear in `caveats` and `evidence_summary`; prose cannot suppress it.

Response envelope:

```json
{
  "result": { "schema_version": "oh_god.v1" },
  "source": "model | deterministic_fallback",
  "model": "string or null",
  "freshness": {
    "stale": false,
    "generated_for_pick": 31,
    "current_pick": 31,
    "generated_revision": "revision",
    "current_revision": "revision",
    "options_available": true
  },
  "latency_ms": 123,
  "timeout_seconds": 5
}
```

## 3. Deterministic context supplied to the model

Proposed context schema version: `oh_god_context.v1`.

```json
{
  "schema_version": "oh_god_context.v1",
  "draft": {
    "revision": "session.updated_at",
    "current_pick": 31,
    "current_team": 7,
    "user_team": 3,
    "is_user_pick": false,
    "next_user_pick": 33,
    "following_user_pick": 48,
    "picks_until_user": 2,
    "round": 4
  },
  "league": {
    "scoring": "half_ppr",
    "league_size": 10,
    "rounds": 15,
    "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
    "bench_size": 6
  },
  "board_health": {
    "snapshot_status": "ready",
    "source_status": "ready",
    "freshness_status": "warning",
    "generated_at": "ISO timestamp",
    "retrieved_at": "ISO timestamp or null",
    "news_source": "string",
    "warning_codes": ["bounded codes"],
    "warning_count": 1
  },
  "user_roster": {
    "players": ["compact player facts"],
    "position_counts": {"QB": 0, "RB": 2, "WR": 1, "TE": 0},
    "open_starter_slots": {"QB": 1, "RB": 0, "WR": 1, "TE": 1, "FLEX": 1},
    "warnings": ["bounded deterministic warnings"]
  },
  "recent_draft": {
    "selections": ["last 8 compact events"],
    "position_run": {"window": 6, "counts": {}, "positions": []},
    "adp_behavior": {"fallers": [], "reaches": []}
  },
  "before_next_user_pick": {
    "picks": [{"overall_pick": 32, "team": 8}],
    "teams": [{"team": 8, "position_counts": {}, "likely_needs": []}]
  },
  "position_state": {
    "QB": {"available": 20, "best_tier": 2, "remaining_in_tier": 4, "next_tier": 3},
    "RB": {},
    "WR": {},
    "TE": {}
  },
  "candidates": [
    {
      "player_id": "WR:example",
      "player": "Example Player",
      "position": "WR",
      "team": "TST",
      "model_score": 201.2,
      "score_gap_from_leader": 0.0,
      "close_to_leader": true,
      "forecast_points": 250.0,
      "forecast_uncertainty": "known | estimated | missing",
      "vorp": 51.2,
      "tier": 2,
      "players_left_in_tier": 2,
      "adp": 35.0,
      "adp_delta_at_current_pick": 4.0,
      "survival_to_next_pick": 0.22,
      "bye_week": 9,
      "risk": {},
      "flags": [],
      "news": {"freshness": "unknown", "injury_flag": false},
      "reasons": ["bounded deterministic conclusions"]
    }
  ],
  "deterministic_assessment": {
    "primary_player_id": "WR:example",
    "safe_player_id": "RB:example",
    "upside_player_id": "TE:example",
    "urgency": "medium",
    "situation_type": "value_fall",
    "can_wait": "risky",
    "close_score_threshold": 5.0,
    "leader_gap": 2.1
  },
  "constraints": {
    "available_player_ids": ["bounded set of IDs represented in candidates"],
    "state_mutation_allowed": false,
    "max_options": 3,
    "max_caveats": 3,
    "must_disclose_warning_codes": ["codes"]
  }
}
```

The context contains derived facts only, not the full board or raw historical/news documents. Candidate breadth should cover the top deterministic candidates plus position leaders without becoming a raw dump.

## 4. Route and frontend state flow

### Patch 1 routes

- `GET /api/v1/health`: return authoritative runtime board health split into snapshot/source/freshness components. Existing sessions remain readable even when new-session readiness is blocked.
- `GET /api/v1/board/summary`: return the same authoritative health object and metadata used by health/session creation.
- `POST /api/v1/sessions`: reject creation with structured `board_not_ready` (409, recoverable) if authoritative runtime status is not ready. Do not alter existing session routes.

### Patch 3 routes (design only)

- `POST /api/v1/sessions/{name}/assistant/oh-god`: explicit-only inference using the current revision and bounded context.
- `POST /api/v1/sessions/{name}/assistant/oh-god/follow-up`: accepts one enumerated follow-up intent plus the originating revision; never accepts arbitrary mutation commands.
- Existing `assistant/ask` can back Talk shop initially, with a tighter UI and the same stale envelope.

### Frontend state flow

```text
load board summary
  -> render authoritative board badge/date
  -> enable Create only when health.can_create_session

load existing session
  -> always allowed from its saved snapshot
  -> no external call
  -> render tracking state

tap OH GOD (Patch 3)
  -> capture current session revision
  -> disable only OH GOD button; pick entry remains enabled
  -> POST explicit request
  -> if response revision differs: mark stale, refresh state, offer Try again
  -> else render compact card and contextual follow-ups

network failure
  -> retain last confirmed cockpit
  -> mark server unreachable
  -> state whether the attempted operation is confirmed or uncertain
  -> preserve mutation request ID for an explicit retry
```

Patch 1 removes automatic strategy invocation. The existing manual strategy endpoint remains available for compatibility but is not invoked on load, refresh, visibility changes, or pick changes.

## 5. File-by-file implementation plan

### Patch 1 — implement now

- `src/fantasy_draft/board/builder.py`
  - Add a runtime health composer that separates immutable snapshot health, source validation, and freshness.
  - Avoid mutating board JSON; return one authoritative report with `status` and `can_create_session`.
- `src/fantasy_draft/api/dependencies.py`
  - Expose the shared runtime board-health service if dependency injection keeps route use consistent.
- `src/fantasy_draft/api/routes/health.py`
  - Replace embedded-health echo with authoritative runtime report.
- `src/fantasy_draft/api/routes/board.py`
  - Return the identical authoritative report.
- `src/fantasy_draft/api/routes/sessions.py`
  - Gate only new session creation; preserve all existing-session reads/mutations.
- `src/fantasy_draft/api/errors.py`
  - Add a specific recoverable `board_not_ready` mapping.
- `src/fantasy_draft/api/schemas.py`
  - Make the health shape explicit enough for the split statuses.
- `frontend/assets/app.js`
  - Render authoritative board state/date and disable new-session creation consistently.
  - Remove every automatic strategy trigger while retaining explicit Analyze behavior for compatibility.
  - Translate network errors into actionable “last confirmed state” language.
- `frontend/index.html`
  - Adjust compact readiness copy only if needed; no Patch 3 cockpit redesign yet.
- `tests/conftest.py`
  - Give API fixtures a real normalized projection CSV/manifest so they are runtime-valid.
- `tests/test_api.py`, `tests/test_projection_validator.py`
  - Cover health split, invalid-board creation blocking, existing-session access, and restore current failing imports/contracts.
- `tests/test_browser_smoke.py`
  - Assert no automatic strategy request and actionable offline copy where feasible.
- `README.md`, `docs/components/web-api.md`
  - Document authoritative health semantics and existing-session exception.

### Patch 3 — design only, do not implement now

- `src/fantasy_draft/assistant/copilot.py`: bounded context, deterministic fallback, strict response validation, staleness envelope.
- `src/fantasy_draft/api/schemas.py`: typed OH GOD request/response/follow-up schemas.
- `src/fantasy_draft/api/routes/sessions.py`: explicit OH GOD and follow-up routes.
- `src/fantasy_draft/draft/recommendations.py`: expose derived candidate evidence without rewriting weights.
- `frontend/index.html`: replace persistent plan/recommendation wall with OH GOD card and collapsed Talk shop drawer.
- `frontend/assets/app.js`: explicit-only copilot state machine; follow-up intents; stale response handling.
- `frontend/assets/app.css`: restrained OH GOD emphasis, compact card, drawer, portrait/landscape behavior.
- `tests/test_copilot.py`, `tests/test_api.py`, `tests/test_browser_smoke.py`: allowlist, fallback, timeout, stale revision, explicit-only request, close-call copy, mobile layout.
- `docs/components/model-reasoning-layer.md`, `README.md`: modes and reasoning boundaries.

## 6. Conflicts and ambiguities discovered

1. **Portable snapshot versus source-required validation:** the board is designed as a self-contained session snapshot, but runtime validation requires a raw CSV that `.gitignore` excludes. Patch 1 can correctly block false-green creation, but making a clean checkout usable requires the separate Patch 2 packaging/fingerprint decision.
2. **Snapshot/source/freshness definitions:** snapshot validity means the board contract and embedded build-time validation are sound; source validity means the referenced normalized source and manifest are readable/schema-valid; freshness means the manifest age is within policy. Overall creation readiness should require all three. Existing sessions use their saved snapshot and remain accessible.
3. **Current API fixtures are not runtime-valid:** most test boards omit `metadata.projection_source` and a source manifest. Tests must construct realistic source artifacts rather than weakening runtime checks.
4. **Current board health is time-dependent:** the checked manifest is near its 14-day limit on the audit date. Tests must inject a clock or write a current manifest; production health should report the validation timestamp.
5. **Launcher consistency:** the Bash launcher already fails on CLI validation. Patch 1 mainly aligns direct server/API/UI behavior; Windows deployment remains Patch 2 scope.
6. **Automatic strategy versus manual compatibility:** Patch 1 removes automatic calls but retains the manual button/endpoint. Patch 3 will replace that presentation with OH GOD; removing the endpoint now would broaden the patch and break compatibility.
7. **“Model/data lean” ownership:** structured output calls the primary a model/data lean, but deterministic ranking remains authoritative input. The model may select only among allowlisted candidates and must not silently override unavailable-state or data warnings.
8. **Talk-shop input versus no typing on the clock:** the drawer may allow typing only when explicitly opened. It should collapse or visually recede on the user’s turn; OH GOD remains the no-typing pressure path.

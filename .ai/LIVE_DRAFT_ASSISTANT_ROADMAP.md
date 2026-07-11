# Live Fantasy Draft Assistant Roadmap

**Status:** Active implementation plan  
**Product direction:** Position-first draft intelligence with a live conversational assistant  
**Last updated:** 2026-07-10

## 1. Product Vision

Build a draft-night application that separates reliable facts from model reasoning:

1. The data pipeline supplies current projections, ADP, historical performance,
   player identity, news, risk, and bye weeks.
2. A deterministic engine produces auditable player priorities and evaluates live
   draft conditions.
3. A stateful draft session records every selection and roster.
4. A language model explains tradeoffs and answers questions using only the board,
   league configuration, and live state supplied by the application.

Snake-order planning is secondary. The primary product is a trustworthy top-N board
for each role and a live assistant that can answer questions such as:

- Who should I prioritize at RB, WR, QB, and TE?
- Who is the best choice right now?
- Can I wait at quarterback or tight end?
- Is a position run happening?
- Which tier is about to disappear?
- What safe, balanced, and upside choices do I have?

## 2. Design Principles

- **Facts stay deterministic.** The model must not invent projections, rankings,
  availability, news, or draft state.
- **Every recommendation is explainable.** Preserve the inputs and signals that led
  to a result.
- **The app works without the model.** Draft-state management and deterministic
  recommendations must remain available during an API or internet outage.
- **Unsafe data is visible.** Missing, stale, fallback, or conflicting data marks the
  board as not ready for live advice.
- **State changes are explicit and reversible.** Draft, undo, correction, save, and
  resume operations cannot depend on natural-language interpretation alone.
- **One engine, multiple interfaces.** CLI, future browser UI, and model tools consume
  the same schemas and services.
- **Manual draft entry comes first.** Platform integrations are optional later work,
  after the local workflow is dependable.

## 3. Target Architecture

```text
Historical stats   Projections   ADP   News/risk   Player identity
        \               |         |       |              /
                         Data pipeline
                              |
                   Position-first draft board
                              |
                Deterministic recommendation engine
                              |
       League config + live draft state + recent selections
                              |
                  Controlled model context/tools
                              |
                    CLI first, local web UI later
```

Long-term module shape:

```text
draft_assistant/
  config.py
  schemas.py
  board/
    builder.py
    rankings.py
    validation.py
  data/
    projections.py
    adp.py
    history.py
    news.py
    identity.py
  draft/
    session.py
    state.py
    availability.py
    recommendations.py
  assistant/
    context.py
    client.py
    prompts.py
    response_validation.py
```

Migration can be incremental. Useful existing scripts do not need to be rewritten
until their behavior moves behind a stable boundary.

## 4. Stable Data Contracts

### League configuration

The league contract must eventually cover:

- League name and team count
- Standard, half-PPR, or PPR scoring
- Scoring bonuses and custom rules
- Starting QB, RB, WR, TE, FLEX, and Superflex slots
- Bench and reserve slots
- Draft type and optional keeper settings

### Draft board

The board contains:

- Schema version and generation metadata
- Target season and source timestamps
- Projection, ADP, news, and identity sources
- Health status and validation issues
- Independent top-N QB, RB, WR, and TE lists
- Optional FLEX and Superflex views
- Player rank, tier, projections, VORP, ADP, bye, risk, news flags,
  confidence, and auditable scoring evidence

### Draft state

The live state will contain:

- Session identifier and timestamps
- League configuration reference
- Current pick and round
- Ordered selection history
- Available and drafted player identifiers
- Every team's roster
- User-controlled team identifier
- Undo/correction history
- Autosave version

### Recommendation response

Deterministic and model-assisted recommendations should share a structured shape:

```json
{
  "primary": "Player A",
  "alternatives": ["Player B", "Player C"],
  "strategy": "balanced",
  "confidence": 0.84,
  "signals": {
    "roster_need": "RB",
    "tier_drop_imminent": true,
    "position_run": false,
    "survival_to_next_pick": 0.21
  },
  "reasons": [
    "Last remaining RB in the current tier",
    "Comparable wide receivers remain available"
  ]
}
```

## 5. Implementation Phases

## Phase 1 — Position-First Board MVP

**Status: Implemented; blocked from live-ready status by missing projection source.**

Delivered:

- `scripts/draft_board.py`
- Versioned `outputs/draft_board.json` contract
- League metadata
- Independent QB, RB, WR, and TE rankings
- Default role limits: QB 20, RB 50, WR 60, TE 20
- Player evidence, news, risk, VORP, ADP, tier, and projection fields
- Board health validation
- CLI build, show, and validate commands
- Unit and end-to-end tests

Commands:

```bash
python scripts/cli.py --build-board --league-size 10 --scoring half_ppr
python scripts/cli.py --show-board --position RB --top 10
python scripts/cli.py --validate-board
```

Remaining exit criterion:

- Restore or replace the missing `data/players_2026_positions_bye.csv` source and
  produce a board whose `health.status` is `ready`.

## Phase 2 — Projection and Data Reliability

**Status: Core work complete.** The primary provider now parses the full official
ESPN Mike Clay projection guide and merges it with FantasyPros ADP/bye context.
Scoring conversion is explicit, source metadata is attributable, a provider-neutral
CSV importer is available, and the generated board passes readiness validation.

**Goal:** Make the position board reproducible and trustworthy.

Work:

- Choose dependable current-season projection and ADP sources.
- Separate historical performance from future projections.
- Normalize player names, suffixes, team abbreviations, rookies, and free agents.
- Assign stable internal player identifiers where possible.
- Record retrieval timestamps and source versions.
- Validate player/team combinations and duplicate identities.
- Check projection coverage, bye-week coverage, and positional coverage.
- Detect stale sources individually rather than only checking final output.
- Keep historical fallback diagnostic-only.
- Add a concise data-health command and report.
- Make scoring-format transformations explicit and testable.

Delivered so far:

- Season-aware projection fetch CLI
- Source and retrieval-time manifest
- Published-versus-estimated provenance on every row
- Coverage, duplicate, missing field, staleness, and team-conflict checks
- Projection health propagated into draft-board health
- Projection provenance exported through rankings into player board records
- Tests for good, stale, estimated, and malformed inputs
- Full ESPN PDF adapter for QB, RB, WR, and TE projections
- Deterministic PPR, half-PPR, and standard conversion from projected receptions
- Conservative cross-provider player identity normalization and aliases
- Licensed/user-supplied CSV import fallback

Acceptance criteria:

- A clean checkout can reproduce the board using documented commands.
- Essential sources are current, attributable, and locally verifiable.
- Conflicts are reported with actionable player-level detail.
- A board cannot be marked ready when it uses historical results as projections.
- Representative player projections and team assignments pass fixture checks.

## Phase 3 — Live Draft State Engine

**Status: Core engine implemented.** Ready-board snapshots, event-backed selections,
undo, snake ownership, all-team rosters, safe player matching, atomic autosave,
resume, and noninteractive CLI queries are operational. Bulk entry and arbitrary
historical correction remain later usability enhancements.

**Goal:** Reliably record and recover an entire draft without a model.

Work:

- Create new, save, resume, list, and close session operations.
- Track current pick, round, selections, availability, and every team roster.
- Add `draft`, `undo`, and correction operations.
- Add fuzzy player search with explicit ambiguity handling.
- Autosave atomically after every state change.
- Store append-only events or sufficient history for safe undo and auditing.
- Allow bulk entry when several picks were missed.
- Reject duplicate selections and invalid team/pick transitions.
- Support manual override without silently corrupting state.

Initial CLI experience:

```text
new-draft
draft "Jahmyr Gibbs" --team 1
draft "Ja'Marr Chase" --team 2
available RB
roster mine
undo
save
resume
```

Acceptance criteria:

- A draft survives process termination and resumes exactly.
- Undo restores availability, roster, and pick position.
- Ambiguous or unknown player names never silently select the wrong player.
- Duplicate drafting is prevented.
- State operations have focused unit tests and full-draft simulations.

Delivered:

- Versioned draft-session JSON contract
- Immutable board snapshot per session
- Atomic persistence and load-time event validation
- Draft, undo, status, roster, availability, and session-list commands
- Exact, prefix, and conservative fuzzy player matching
- Explicit ambiguity and unavailable-player errors
- Snake-order pick ownership and next-user-pick calculation
- Board depth validation against planned draft size

## Phase 4 — Deterministic Recommendation Engine

**Goal:** Produce useful draft-night choices even when no model is available.

Capabilities:

- Best available overall and by position
- Remaining players and counts by tier
- Position scarcity and tier-drop alerts
- Roster need and starter-slot coverage
- FLEX and Superflex eligibility
- Safe, balanced, and upside recommendation modes
- Position-run detection from recent selections
- Picks until the user's next selection
- Estimated probability that a player survives to the next pick
- Bye-week concentration warnings as a secondary signal

Rules:

- Never choose solely because a player's ADP is closest to the current pick.
- Keep board priority, VORP, tier scarcity, roster need, and availability as
  separate inspectable signals.
- Avoid forcing positional balance when elite value is available.
- Do not overreact to runs; measure the next tier and replacement cost.

Acceptance criteria:

- Every recommendation includes structured signals and concise reasons.
- Results remain deterministic for the same board, config, and draft state.
- Tests cover early, middle, and late picks across league formats.
- The fallback experience is useful enough to finish a draft offline.

## Phase 5 — Model Reasoning Layer

**Goal:** Add conversational judgment without giving the model ownership of facts.

Work:

- Create a compact context builder from board, league, state, and deterministic
  recommendation output.
- Send only relevant available candidates rather than all player records.
- Define model tools for read-only queries and explicit state mutations.
- Require structured model responses and validate them before display.
- Prevent recommendations of unavailable or unknown players.
- Preserve OpenRouter as the initial provider abstraction.
- Add timeouts, retries, cost/token limits, and deterministic fallback.
- Log recommendation inputs and structured outputs without logging secrets.
- Make uncertainty and data-health limitations visible in responses.

Model responsibilities:

- Explain recommendations and tradeoffs.
- Compare players requested by the user.
- Respond to strategy and risk preferences.
- Answer counterfactual questions.
- Disagree with the deterministic primary only when supplied evidence supports it.

The model must not:

- Invent player facts, news, projections, or selections.
- Change draft state through unvalidated prose.
- Recommend a drafted player.
- conceal that the board is not ready.

Acceptance criteria:

- Responses parse against the recommendation schema.
- Every named candidate exists and is available.
- API failure immediately falls back to deterministic advice.
- Context size and response latency are suitable for live picks.

## Phase 6 — Draft-Night CLI

**Goal:** Combine board, state, recommendations, and chat into a fast terminal UI.

Desired display:

```text
Pick 28 | Next pick 37 | Roster RB, WR, WR

Best available
1. Player A — RB — Tier 2
2. Player B — TE — Tier 2
3. Player C — WR — Tier 3

Tier alerts
RB: 1 remaining in Tier 2
TE: 2 remaining in Tier 2

Assistant
Take Player A. This is the final RB in the current tier, and comparable
receivers are likely to remain at your next pick.

> drafted Player A
```

Work:

- Interactive loop with command history and help.
- Quick draft entry and keyboard-friendly corrections.
- Compact roster, availability, tier, and recent-pick panels.
- Explicit online/offline and board-health indicators.
- Natural-language questions alongside structured commands.
- Optional noninteractive commands for scripting and tests.

Acceptance criteria:

- Common actions require minimal typing.
- The screen remains readable on a laptop at a live draft.
- The user can continue when the model or network is unavailable.
- Mistakes can be corrected in seconds.

## Phase 7 — Draft Simulation and Hardening

**Goal:** Test behavior under realistic draft pressure and failure modes.

Simulation matrix:

- 8-, 10-, and 12-team leagues
- Standard, half-PPR, and PPR
- FLEX and Superflex
- Early, middle, and late draft slots
- Position runs and unexpected reaches
- Major ADP fallers
- Missing or conflicting projections
- Ambiguous player names
- Duplicate and out-of-order entry attempts
- Undo and crash recovery
- Model/API unavailable or malformed response
- Stale or not-ready board

Evaluate:

- Recommendation latency
- Roster construction and starter coverage
- Value captured relative to board and ADP
- Position-run response quality
- Nonsensical or unavailable-player recommendation rate
- Recovery time after an incorrect entry
- Model token usage and cost

Acceptance criteria:

- Complete simulated drafts finish without state corruption.
- Critical workflows have regression fixtures.
- Recommendation latency fits typical live pick timers.
- Known failure modes produce actionable messages and safe fallback behavior.

## Phase 8 — Local Browser UI

**Goal:** Provide a more visual draft-night interface after the engine is proven.

Potential interface:

- Position and tier board columns
- Search and one-click drafting
- All team rosters
- Recent picks and position-run visualization
- Chat and recommendation panel
- Undo/correction controls
- Data-health, autosave, and connectivity indicators
- Local-only server by default

Rules:

- Reuse the same board, state, and recommendation services as the CLI.
- Do not move domain logic into browser components.
- Preserve terminal support as the reliable fallback.

Acceptance criteria:

- Browser and CLI produce identical state transitions and recommendations.
- Refreshing the browser does not lose draft state.
- The UI remains usable on a laptop without external hosting.

## Phase 9 — Optional Platform Integrations

Only consider after the manual workflow is reliable:

- Draft result import/export
- Read-only league configuration import
- Platform-specific draft synchronization where stable APIs permit it
- Multiple board/provider adapters
- Post-draft roster analysis

Platform access must degrade gracefully and never become required for the core app.

## 6. Recommended Delivery Order

1. Finish Board MVP readiness by repairing projections and identity validation.
2. Build the live draft state engine.
3. Add deterministic recommendations.
4. Add model reasoning over controlled context.
5. Harden the terminal workflow through simulations.
6. Build a local browser UI.
7. Evaluate optional platform integrations.

## 7. Immediate Next Work

The next implementation session should begin with Phase 2:

1. Audit `fetch_2026_projections.py` and choose the supported projection source.
2. Make projection acquisition produce a documented, reproducible artifact.
3. Add source timestamp and coverage validation.
4. Add player identity/team conflict reporting.
5. Regenerate rankings and `draft_board.json`.
6. Require `python scripts/cli.py --validate-board` to return success before
   beginning live-state work.

Once the board is genuinely ready, start Phase 3 with event-backed draft sessions,
autosave, draft/undo, availability, and roster views.

## 8. Current Known Risks

- The checked-in ranking metadata references a missing Windows-style projection path.
- Current projections and some player/team records have not been independently
  validated.
- `nfl_data_py` historical endpoints did not provide 2025 seasonal or weekly data in
  the tested environment.
- Apple Python 3.9 uses LibreSSL and emits an urllib3 compatibility warning; the
  documented target remains Python 3.12.
- Existing recommendation logic overweights nearby ADP and should not become the
  foundation of the new deterministic engine.
- News signals should remain capped advisory evidence, not dominate rankings.

## 9. Definition of Draft-Night Ready

The product is ready to bring to a real draft when:

- The board health status is `ready` with current, attributable projections.
- Position priorities and representative player records have been reviewed.
- Draft sessions autosave and recover without corruption.
- Draft, undo, correction, availability, and roster workflows are fast and tested.
- Deterministic recommendations work offline.
- The model cannot recommend unavailable players or mutate state without validation.
- Full draft simulations pass across the target league configuration.
- The UI clearly displays stale data, connectivity loss, and fallback mode.
- A short draft-night runbook documents startup, recovery, and emergency commands.

# NFL Fantasy Draft Assistant

A data-driven fantasy football draft engine with live session tracking,
VORP-based recommendations, and an optional OpenRouter reasoning layer.

The project includes a command-line application and a private, mobile-first web
cockpit hosted on the user's PC. The repository remains the source of truth for
projections, rankings, availability, draft state, and recommendations; the browser is
a fast interface over the same tested domain code.

## Product Direction

```text
Historical data + projections + ADP + news/risk
                        |
                        v
              VORP-based player rankings
                        |
                        v
                Position-first draft board
                        |
                        v
         Live session + deterministic advice
                        |
              +---------+---------+
              |                   |
         CLI today       Mobile web cockpit next
                                  |
                         Private Tailscale access
```

The guiding rules are:

- Player facts and draft state remain deterministic and auditable.
- The model explains recommendations; it does not own availability or mutate state.
- Every selection is explicit, validated, autosaved, and reversible.
- The complete draft remains usable when OpenRouter is unavailable.
- The future web server binds locally and is shared privately with Tailscale Serve,
  not exposed through a public tunnel.

See [.ai/LIVE_DRAFT_ASSISTANT_ROADMAP.md](.ai/LIVE_DRAFT_ASSISTANT_ROADMAP.md) for the
mobile architecture, API contracts, implementation milestones, and definition of
draft-night readiness.

## What Works Today

### Data and rankings

- Historical seasonal and weekly NFL data ingestion
- Current-season projection acquisition or CSV import
- Projection provenance, freshness, coverage, and identity validation
- Explicit standard, half-PPR, and PPR conversion
- Weighted historical performance and availability features
- Position-aware age, consistency, usage, team, risk, and news signals
- VORP calculation and auditable score breakdowns
- Versioned player rankings and position-first draft board

### Live draft engine

- Crash-safe, event-backed draft sessions
- Snake-order pick ownership and every-team rosters
- Exact, prefix, and conservative fuzzy player matching
- Duplicate and unavailable-player prevention
- Atomic autosave after every state change
- Undo and session recovery
- Best available players by position
- Safe, balanced, and upside recommendation modes
- Tier cliffs, roster needs, recent position runs, and next-pick survival estimates

### Optional model reasoning

- Small, bounded evidence packet rather than the entire board
- Available-player allowlist
- Structured and validated model responses
- Read-only questions and player comparisons
- Immediate deterministic fallback on API, timeout, or validation failure

## Current Status

The analytical pipeline, draft board, live state engine, deterministic recommender,
OpenRouter reasoning layer, and terminal draft dashboard are implemented.

The packaged runtime, cockpit read model, versioned FastAPI API, interactive mobile
page, browser session management, safe mutation controls, and controlled conversational
assistant are implemented. The active delivery sequence is now:

1. Deploy privately through Tailscale Serve.
2. Complete full phone-based draft simulations.

## Installation

### Requirements

- Python 3.12
- A virtual environment
- An OpenRouter API key only if model-assisted answers are desired
- Tailscale on the PC and phone only when the private web interface is implemented

### Setup

```bash
git clone <repository-url>
cd ai-nfl-fantasy-draft

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

Copy the environment template and add your own OpenRouter credentials if needed:

```bash
cp .env.example .env
```

```dotenv
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=your-preferred-fast-model
OPENROUTER_APP_TITLE=NFL Fantasy Draft Assistant
```

`.env` is ignored by Git. Never place its values in frontend code, committed session
files, logs, or screenshots.

## Quick Start

### 1. Validate the checked-in board

```bash
python scripts/cli.py --validate-board
python scripts/cli.py --show-board --top 10
```

Do not start a real draft from a board whose health status is `not_ready`. Warnings
remain available for inspection, but errors indicate that projections, coverage, or
the board contract are unsafe for live advice.

### 2. Create a live session

```bash
python scripts/live_draft.py new home-league \
  --league-size 10 \
  --rounds 15 \
  --user-team 5
```

The session snapshots the validated board and saves to
`sessions/home-league.json`.

### 3. Run the draft-night terminal

```bash
python scripts/live_draft.py interactive home-league
```

The terminal shows:

- Current pick and team
- Your next pick
- Your roster
- Recent selections
- Best available players
- Imminent tier drops
- Deterministic recommendation
- Model and autosave status

State changes always require explicit `draft` or `undo` commands. Ordinary sentences
are treated as read-only assistant questions.

### 4. Run privately on a phone

With Tailscale installed and connected on the PC and phone, start the checked private
deployment:

```bash
scripts/draft-night-server start
```

The command validates the board, binds FastAPI to localhost, configures private
Tailscale Serve, and prints the phone URL. See the
[draft-night runbook](docs/draft-night-runbook.md) for verification, recovery, and
shutdown instructions.

Generate the static emergency board before draft night:

```bash
venv/bin/python scripts/generate_emergency_cheatsheet.py
```

The printable fallback is written to `outputs/emergency_draft_cheatsheet.md`. It does
not track selections; cross off drafted players manually.

## Live Draft Commands

Record and reverse selections:

```bash
python scripts/live_draft.py draft home-league "Jahmyr Gibbs"
python scripts/live_draft.py undo home-league
```

Inspect the active session:

```bash
python scripts/live_draft.py status home-league
python scripts/live_draft.py available home-league --position RB --top 10
python scripts/live_draft.py roster home-league
python scripts/live_draft.py roster home-league --team 3
python scripts/live_draft.py list
```

Get deterministic advice:

```bash
python scripts/live_draft.py recommend home-league --mode balanced
python scripts/live_draft.py recommend home-league --mode upside --json
```

Supported modes are:

- `safe`: applies stronger risk penalties
- `balanced`: combines board value, VORP, need, scarcity, and risk
- `upside`: gives more weight to VORP and upside signals

Ask the optional model reasoning layer:

```bash
python scripts/live_draft.py ask home-league \
  "Who should I take, and can I wait at quarterback?" \
  --mode balanced
```

Use `--json` for the validated response contract, `--model` to override the configured
OpenRouter model, or `--timeout` to change the request timeout. If the model cannot
produce a valid answer, the command returns deterministic fallback advice.

## Mobile Web Cockpit

Start the local server:

```bash
draft-server
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) on the PC. The preview uses
the first saved session by default. Select a specific session with:

```text
http://127.0.0.1:8000/?session=home-league
```

The fixed textbox accepts conservative pick phrases such as:

```text
someone got Gibbs
Gibbs picked
they took Ja'Marr Chase
draft Puka Nacua
```

Use **Drafts** in the header to resume any saved session or create a new one. The last
opened session is remembered on that browser. New sessions use only the server's
configured ready board; the form derives sensible team and round limits from board
capacity. Creation retries are idempotent, while a duplicate name from a different
request is rejected without overwriting the existing draft.

Each saved draft also has a delete control. Deletion requires an exact-session
confirmation showing its current pick and recorded-selection count. The JSON is moved
to `sessions/.trash/` rather than permanently erased. Deleting the active session
automatically resumes the next saved draft or opens the new-draft form.

The main navigation provides four mobile views:

- **Cockpit** keeps the current recommendation and quick draft controls above the fold.
- **Board** groups the full session board by position and tier, hiding drafted players
  by default. Tap any player for projection, VORP, ADP, historical evidence, risk, and
  flags; available players can enter the normal confirmation flow from that sheet.
- **Roster** shows starter openings, FLEX eligibility, selection details, and bye-week
  conflicts for the user's team.
- **Draft log** preserves the complete selection history, including undone picks, with
  team and position filters.

These views refresh on entry, after state changes, through the refresh button, and when
the browser returns to the foreground. The private single-user deployment intentionally
does not add websocket infrastructure without evidence that polling is needed.

The recommendation, alternatives, best-available rows, and debounced player search
all open the same exact player, overall pick, and team confirmation. Draft state
changes only after confirmation. Unique last names are accepted; ambiguous names
return candidate choices without changing state. Retries and double taps use an
idempotency key so the same request cannot advance the draft twice, and a confirmation
is rejected if the overall pick has advanced since it opened.

The cockpit shows the current team on the clock, the user's countdown, tier cliffs,
recent position runs, and separate board, model, autosave, and server-connectivity
health indicators.

Use **Undo last** to review the exact player, pick, position, and team before restoring
that player to the pool. The confirmation is rejected if another pick arrives first.
Use **Catch up** to enter 2–20 missed selections separated by commas, semicolons, or
new lines. The app resolves and previews the full ordered batch, then saves every pick
atomically. If any player is ambiguous, unavailable, or invalid, no picks are saved.

Ordinary questions use the same bounded assistant as `live-draft ask`. The result card
shows whether advice came from the configured model or deterministic local fallback,
plus request latency. Calls have a 12-second server timeout and can be ignored with
the UI's Cancel button. If a pick lands while an answer is in flight, the answer is
marked stale, draft state refreshes, and the user is prompted to ask again.

The implemented API includes:

```text
GET /api/v1/health
GET /api/v1/board/summary
GET /api/v1/sessions
POST /api/v1/sessions
GET /api/v1/sessions/{name}
DELETE /api/v1/sessions/{name}
GET /api/v1/sessions/{name}/cockpit
GET /api/v1/sessions/{name}/board
GET /api/v1/sessions/{name}/roster
GET /api/v1/sessions/{name}/draft-log
GET /api/v1/sessions/{name}/players/search
GET /api/v1/sessions/{name}/players/{player_id}
GET /api/v1/sessions/{name}/available
GET /api/v1/sessions/{name}/recommendation
POST /api/v1/sessions/{name}/commands/interpret
POST /api/v1/sessions/{name}/assistant/ask
POST /api/v1/sessions/{name}/picks
POST /api/v1/sessions/{name}/picks/bulk/preview
POST /api/v1/sessions/{name}/picks/bulk
POST /api/v1/sessions/{name}/undo
```

Interactive API documentation is available at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). The server binds to
localhost by default. The OpenRouter key remains server-side and is never included in
browser traffic or static assets.

## Build or Refresh the Draft Board

### Full pipeline

```bash
python scripts/cli.py --pipeline
```

For a faster run that does not refresh news:

```bash
python scripts/cli.py --pipeline --skip-news
```

The pipeline ingests historical data, calculates ranking features and VORP, and writes
freshness metadata with the rankings.

### Projection acquisition

Fetch and validate the target season's projection and ADP inputs:

```bash
python scripts/cli.py --fetch-projections --season 2026 --scoring half_ppr
python scripts/cli.py --validate-projections --season 2026
```

The default provider combines full-season ESPN Mike Clay projections with
FantasyPros DraftWizard ADP and bye-week context. Published PPR totals are converted
to the selected scoring format using projected receptions. The legacy partial
FantasyPros adapter remains available for diagnostics:

```bash
python scripts/cli.py --fetch-projections \
  --season 2026 \
  --scoring half_ppr \
  --projection-provider fantasypros
```

Import licensed or manually maintained projections without changing code:

```bash
python scripts/cli.py --import-projections path/to/projections.csv \
  --season 2026 \
  --scoring half_ppr
```

The importer accepts common aliases such as `player_name`, `pos`, `fpts`, `rk`, and
`bye`. Player name, position, and projected fantasy points are required.

### Ranking and board generation

Generate rankings from existing data, then build and inspect the position board:

```bash
python scripts/cli.py --rank-only
python scripts/cli.py --build-board --league-size 10 --scoring half_ppr
python scripts/cli.py --validate-board
python scripts/cli.py --show-board --position WR --top 15
```

`outputs/draft_board.json` defaults to 20 QB, 50 RB, 60 WR, and 20 TE entries. Use
`--board-top N` to apply one custom limit to each position.

## Canonical Outputs

### `outputs/player_rankings.json`

The detailed analytical output. It includes projection and historical inputs, total
score, VORP, tiers, risk flags, provenance, and the component-level scoring evidence.

### `outputs/draft_board.json`

The stable consumption contract for live draft clients. It contains league metadata,
health status, and independent QB, RB, WR, and TE priority lists with compact player
evidence.

### `sessions/<name>.json`

The authoritative live draft state. It contains the board snapshot, league settings,
selection and undo events, current pick, availability, and rosters. It is atomically
saved after mutations and ignored by Git.

The raw ranking file should not be treated as the live interface. Consumers should
use the validated board plus an active session.

## Architecture and Safety Boundaries

```text
Data pipeline
    -> player rankings
    -> validated position board
    -> draft session
    -> deterministic recommendation
    -> bounded optional model context
```

- `src/fantasy_draft/board/` owns the position-first board contract.
- `src/fantasy_draft/validation/` owns projection and board input validation.
- `src/fantasy_draft/draft/` owns live state, persistence, and deterministic advice.
- `src/fantasy_draft/assistant/` owns bounded model context and response validation.
- `src/fantasy_draft/providers/` owns external service adapters such as OpenRouter.
- `src/fantasy_draft/cli/` owns the packaged live-draft terminal interfaces.

The corresponding files under `scripts/` are compatibility wrappers so existing
commands continue to work. Install the repository in editable mode with
`pip install -e .` before using those wrappers.

The FastAPI layer wraps these modules through a cockpit composition service. HTTP
routes and browser code do not duplicate ranking, availability, or recommendation
logic.

## Private Mobile Cockpit

The target private deployment model is:

```text
Phone browser
    -> private Tailscale HTTPS
    -> Tailscale Serve on the PC
    -> FastAPI bound to localhost
    -> existing draft engine
    -> optional outbound OpenRouter request
```

The mobile UI will prioritize:

- Current pick and picks until the user's turn
- One prominent recommendation and a few alternatives
- Fast player search and explicit pick confirmation
- One-tap position filters
- Tier-drop and position-run alerts
- Recent picks and compact roster state
- Prominent undo with exact confirmation
- Clear board, model, connectivity, and autosave health

The initial frontend uses HTML, CSS, and small JavaScript modules served by the Python
application. An installable PWA is deferred until the interactive mobile flow
succeeds in realistic full-draft simulations.

## Verification

Run the test suite:

```bash
pytest
```

Run the local rankings and recommendation smoke test:

```bash
python scripts/cli.py --smoke-test
```

Verify optional OpenRouter connectivity:

```bash
python scripts/cli.py --openrouter-smoke-test
```

The OpenRouter test requires a configured API key. Deterministic tests and live draft
state must not require model access.

## Documentation

- [Product and implementation roadmap](.ai/LIVE_DRAFT_ASSISTANT_ROADMAP.md)
- [Documentation index](docs/README.md)
- [CLI guide](docs/user-guide/cli-guide.md)
- [Draft board](docs/components/draft-board.md)
- [Live draft session](docs/components/live-draft-session.md)
- [Recommendation engine](docs/components/draft-recommendation-engine.md)
- [Model reasoning layer](docs/components/model-reasoning-layer.md)
- [Draft-night CLI](docs/components/draft-night-cli.md)
- [Private web API](docs/components/web-api.md)

## Contributing

1. Create a focused branch.
2. Preserve unrelated work in the working tree.
3. Add or update tests for behavior changes.
4. Keep domain logic out of interface adapters.
5. Verify deterministic operation without OpenRouter.
6. Update documentation when contracts or workflows change.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

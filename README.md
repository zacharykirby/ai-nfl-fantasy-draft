# NFL Fantasy Draft Forecast CLI

A command-line tool for NFL fantasy football draft analysis and player forecasting using real NFL data from `nfl_data_py`.

## Features

- **Real NFL Data**: Fetches comprehensive player statistics from `nfl_data_py` including:
  - Seasonal and weekly player statistics
  - Roster information (position, team, age, experience)
  - NFL Combine measurements and athletic testing data
  - Fantasy points calculations (PPR scoring)
  - Consistency metrics and performance analysis

- **Data Sources**:
  - Seasonal data (2022-2024 seasons)
  - Weekly game-by-game statistics
  - Player roster information
  - NFL Combine athletic measurements
  - Advanced metrics (target share, air yards, etc.)

- **Player Analysis**:
  - Fantasy points calculation and ranking
  - Position-specific analysis
  - Consistency scoring
  - Experience level categorization
  - Team and season breakdowns

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd nfl-fantasy-draft-forecast-cli
```

2. Set up a Python 3.12 virtual environment:
```bash
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

The CLI provides comprehensive fantasy football analysis with multiple modes and options:

### Live Draft Sessions

Create a crash-safe session from a ready draft board:

```bash
python scripts/live_draft.py new home-league \
  --league-size 10 --rounds 15 --user-team 5
```

Record picks, inspect availability, and correct the latest selection:

```bash
python scripts/live_draft.py draft home-league "Jahmyr Gibbs"
python scripts/live_draft.py available home-league --position RB --top 10
python scripts/live_draft.py status home-league
python scripts/live_draft.py roster home-league --team 5
python scripts/live_draft.py undo home-league
python scripts/live_draft.py recommend home-league --mode balanced
```

Sessions autosave to `sessions/<name>.json` after every mutation. They snapshot the
board used at creation, track all teams in snake order, and preserve selection/undo
events for recovery and auditing. The model is not involved in state changes.

Player matching accepts exact names, unique prefixes, and conservative fuzzy matches.
Ambiguous names return an error and candidate list instead of drafting silently.

Recommendations work without a model or network call. Use `--mode safe`,
`--mode balanced`, or `--mode upside`; add `--json` to receive the full structured
response with score components, roster needs, tier state, position runs, and estimated
survival to the next pick.

Ask the controlled model reasoning layer a draft question:

```bash
python scripts/live_draft.py ask home-league \
  "Who should I take, and can I wait at quarterback?" \
  --mode balanced
```

Add `--json` for the validated response contract or `--model` to override the
configured OpenRouter model. The model receives only a bounded candidate pool, recent
picks, your roster, league settings, and deterministic signals. It cannot mutate the
session. API errors, timeouts, malformed JSON, or unavailable-player recommendations
immediately return deterministic fallback advice.

### Position Priority Board (Primary Workflow)

Build a model-friendly JSON board with independently ranked QB, RB, WR, and TE lists:

```bash
python scripts/cli.py --build-board --league-size 10 --scoring half_ppr
```

This writes `outputs/draft_board.json`. Default list sizes are 20 QB, 50 RB,
60 WR, and 20 TE. Override every position with `--board-top N`.

Inspect priorities or validate whether the underlying inputs are safe for live advice:

```bash
python scripts/cli.py --show-board --position RB --top 10
python scripts/cli.py --validate-board
```

Validation exits nonzero when projections are missing, historical results are being
used as projections, role lists are empty, or the board schema is internally invalid.
The JSON remains available for inspection but its `health.status` will be `not_ready`.

The board is deliberately factual rather than conversational. A live draft client or
model should consume this JSON together with draft state instead of generating its own
player facts.

### Projection Data Health

Fetch the current-season projection/ADP inputs and write a provenance manifest:

```bash
python scripts/cli.py --fetch-projections --season 2026 --scoring half_ppr
python scripts/cli.py --validate-projections --season 2026
```

The fetch writes `data/players_<season>_positions_bye.csv` and
`data/projection_metadata_<season>.json`. Each row identifies whether its projected
points were published by the source or estimated locally from ADP. Validation checks
source age, positional coverage, duplicates, team conflicts, missing fields, and the
share of estimated projections.

The command intentionally exits nonzero when the source does not provide enough real
projections. Do not bypass this result for live advice; either configure a fuller
projection source or treat the generated file as diagnostic data.

The default provider combines full-season ESPN Mike Clay projections with
FantasyPros DraftWizard ADP and bye weeks. ESPN PPR totals are converted to the
selected scoring format using each player's projected receptions. The legacy partial
FantasyPros projection tables remain available for diagnostics with
`--projection-provider fantasypros`.

Licensed or manually maintained projections can be imported without changing code:

```bash
python scripts/cli.py --import-projections path/to/projections.csv \
  --season 2026 --scoring half_ppr
```

The importer accepts common aliases such as `player_name`, `pos`, `fpts`, `rk`, and
`bye`. Player name, position, and projected fantasy points are required.

### Full Pipeline (Recommended)

Run the complete fantasy football analysis pipeline:

```bash
python scripts/cli.py --pipeline
```

This will:
- Fetch and process NFL player data (2022-2024 historical data)
- Analyze player performance and calculate rankings
- Generate VORP (Value Over Replacement Player) scores
- Display top 20 players by VORP
- Show top 7 players for each position (QB, RB, WR, TE)
- Save detailed rankings and freshness metadata to `outputs/player_rankings.json`

### Skip News Analysis

If you want to skip the news fetching and analysis step:

```bash
python scripts/cli.py --pipeline --skip-news
```

### AI-Powered Draft Recommendations

Generate strategic draft recommendations using an OpenRouter model:

```bash
python scripts/cli.py --draft-recommendations
```

This requires:
- `OPENROUTER_API_KEY` set in your environment
- A compatible OpenRouter model (default: `OPENROUTER_MODEL` or `openai/gpt-4o-mini`)
- Fresh rankings with current-season metadata from `python scripts/cli.py --pipeline` or `python scripts/cli.py --rank-only`

#### Custom Draft Recommendations

```bash
# Use a custom OpenRouter model
python scripts/cli.py --draft-recommendations --openrouter-model openai/gpt-4o-mini

# Generate recommendations for an 8-team league from pick 5
python scripts/cli.py --draft-recommendations --top 30 --pick-position 5 --league-size 8

# Save recommendations to file
python scripts/cli.py --draft-recommendations --save-recommendations

# Inspect legacy rankings without treating them as fresh draft advice
python scripts/cli.py --draft-recommendations --allow-stale-rankings
```

### Individual Components

#### Data Ingestion Only

Fetch and process NFL data without running the full pipeline:

```bash
python scripts/cli.py --data-only
```

#### News Analysis Only

Fetch and analyze NFL news sentiment:

```bash
python scripts/cli.py --news-only
```

#### Player Ranking Only

Run player ranking analysis using existing data:

```bash
python scripts/cli.py --ranking
```

#### Player Search

Search for specific player information:

```bash
python scripts/cli.py --player "Patrick Mahomes"
```

### Advanced Options

#### Top N Players

Specify how many top players to display:

```bash
python scripts/cli.py --pipeline --top 50
```

#### Position Filtering

Filter by specific position:

```bash
python scripts/cli.py --pipeline --position QB
```

#### Team Filtering

Filter by specific team:

```bash
python scripts/cli.py --pipeline --team "Kansas City Chiefs"
```

### Environment Setup

For OpenRouter integration, set the environment variable:

```bash
# Windows
set OPENROUTER_API_KEY=your-api-key
set OPENROUTER_MODEL=openai/gpt-4o-mini

# macOS/Linux
export OPENROUTER_API_KEY=your-api-key
export OPENROUTER_MODEL=openai/gpt-4o-mini
```

### Complete Examples

```bash
# Full pipeline with news analysis
python scripts/cli.py --pipeline

# Full pipeline without news (faster)
python scripts/cli.py --pipeline --skip-news

# AI draft recommendations with custom settings
python scripts/cli.py --draft-recommendations --top 40 --pick-position 5 --league-size 8 --save-recommendations

# Player-specific analysis
python scripts/cli.py --player "Christian McCaffrey"

# Data ingestion only
python scripts/cli.py --data-only

# News analysis only
python scripts/cli.py --news-only
```

## Data Structure

The ingested data includes:

- **Player Information**: Name, ID, position, team, age, experience
- **Passing Stats**: Completions, attempts, yards, TDs, interceptions
- **Rushing Stats**: Carries, yards, TDs, fumbles
- **Receiving Stats**: Receptions, targets, yards, TDs
- **Fantasy Metrics**: PPR fantasy points, consistency scores
- **Advanced Metrics**: Target share, air yards share, dominator rating
- **Combine Data**: 40-yard dash, bench press, vertical jump, etc.

## Sample Output

```
✅ Successfully ingested 1725 players
📊 Data saved to: data/nfl_player_data.csv
📋 Summary saved to: data/data_summary.json

Top 5 Players by Position (2024):
QB: Lamar Jackson (BAL): 430.4 points
RB: Saquon Barkley (PHI): 355.3 points
WR: Ja'Marr Chase (CIN): 403.0 points
TE: Brock Bowers (LV): 262.7 points
```

## Dependencies

- `nfl_data_py`: Real NFL data from nflfastR, nfldata, and other sources
- `pandas`: Data manipulation and analysis
- `requests`: HTTP requests for data fetching
- `feedparser`: RSS feed parsing for news
- OpenRouter-compatible model API via `requests`
- `python-dotenv`: Environment variable management
- `tabulate`: Pretty table formatting

## Data Sources

This tool uses `nfl_data_py`, which provides data from:
- **nflfastR**: Play-by-play and advanced statistics
- **nfldata**: Comprehensive NFL datasets
- **DynastyProcess**: Dynasty fantasy football data
- **Draft Scout**: NFL Combine and draft information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **nfl_data_py**: For providing comprehensive NFL data
- **nflfastR**: For the underlying data infrastructure
- **Ben Baldwin, Sebastian Carl, Lee Sharpe**: For making NFL data freely available

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
- Save detailed rankings to `outputs/ranked_all_players.csv`
- Generate ranking summary to `outputs/ranking_summary.json`

### Skip News Analysis

If you want to skip the news fetching and analysis step:

```bash
python scripts/cli.py --pipeline --skip-news
```

### AI-Powered Draft Recommendations

Generate strategic draft recommendations using Ollama LLM:

```bash
python scripts/cli.py --draft-recommendations
```

This requires:
- Ollama running locally (default: http://127.0.0.1:11434)
- A compatible model (default: gemma3)

#### Custom Draft Recommendations

```bash
# Use custom Ollama URL and model
python scripts/cli.py --draft-recommendations --ollama-url http://localhost:11434 --ollama-model llama3

# Generate recommendations for top 30 players over 12 rounds
python scripts/cli.py --draft-recommendations --top 30 --draft-rounds 12

# Save recommendations to file
python scripts/cli.py --draft-recommendations --save-recommendations
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

For Ollama integration, set the environment variable:

```bash
# Windows
set OLLAMA_HOST=127.0.0.1

# macOS/Linux
export OLLAMA_HOST=127.0.0.1
```

### Complete Examples

```bash
# Full pipeline with news analysis
python scripts/cli.py --pipeline

# Full pipeline without news (faster)
python scripts/cli.py --pipeline --skip-news

# AI draft recommendations with custom settings
python scripts/cli.py --draft-recommendations --top 40 --draft-rounds 16 --save-recommendations

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
- `ollama`: Local LLM integration
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
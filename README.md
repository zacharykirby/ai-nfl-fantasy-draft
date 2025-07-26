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

### Data Ingestion

First, fetch and process real NFL data:

```bash
python scripts/data_ingest.py
```

This will:
- Download seasonal data for 2022-2024
- Fetch weekly statistics for consistency analysis
- Get roster information for player details
- Collect NFL Combine data for athletic measurements
- Merge all data sources into a comprehensive dataset
- Save results to `data/nfl_player_data.csv`

### Data Quality Testing

Test the quality of the ingested data:

```bash
python scripts/test_data_ingest.py
```

This provides:
- Data quality analysis
- Missing data assessment
- Top performers by position
- Consistency analysis
- Data structure overview

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
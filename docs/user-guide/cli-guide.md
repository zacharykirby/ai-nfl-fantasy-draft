# 🏈 NFL Fantasy Draft Assistant - CLI Guide

## Overview

The Command Line Interface (CLI) provides a beautiful, user-friendly way to access all the fantasy football analysis functions. It combines data ingestion, news analysis, and player ranking into an intuitive command-line experience.

## 🚀 Quick Start

### 1. Run the Complete Pipeline
```bash
python scripts/cli.py --pipeline
```
This runs the entire analysis:
- Fetches player statistics
- Collects latest fantasy news
- Analyzes news sentiment
- Generates comprehensive rankings

### 2. View Rankings
```bash
# Show top 10 players across all positions
python scripts/cli.py --rankings

# Show top 5 WRs
python scripts/cli.py --rankings --position WR --top 5

# Show QBs sorted by news buzz
python scripts/cli.py --rankings --position QB --sort-by buzz

# Exclude injured players
python scripts/cli.py --rankings --exclude-injured
```

### 3. Get Player Details
```bash
python scripts/cli.py --player "Patrick Mahomes"
```

## 📋 Available Commands

### Main Actions

| Command | Description |
|---------|-------------|
| `--pipeline` | Run the complete fantasy football analysis pipeline |
| `--rankings` | Display player rankings |
| `--player NAME` | Show detailed information about a specific player |
| `--data-only` | Run only data ingestion |
| `--news-only` | Run only news fetching and analysis |
| `--rank-only` | Run only player ranking (requires existing data) |

### Filtering Options

| Option | Description | Values |
|--------|-------------|--------|
| `--position` | Filter by position | QB, RB, WR, TE, K, DST |
| `--top N` | Show top N players | Integer (default: 10) |
| `--exclude-injured` | Exclude injured players | Boolean flag |
| `--sort-by` | Sort rankings by | score, buzz, consistency |

### Pipeline Options

| Option | Description | Default |
|--------|-------------|---------|
| `--years` | Years of data to analyze | 2022 2023 2024 |
| `--news-age` | Max age of news headlines (hours) | 24 |
| `--force-refresh` | Force refresh of existing data | False |

## 🎯 Usage Examples

### Complete Analysis
```bash
# Run full pipeline with custom settings
python scripts/cli.py --pipeline --years 2023 2024 --news-age 48 --force-refresh
```

### View Rankings by Position
```bash
# Top 10 QBs
python scripts/cli.py --rankings --position QB

# Top 5 RBs excluding injured players
python scripts/cli.py --rankings --position RB --top 5 --exclude-injured

# Top 3 WRs sorted by consistency
python scripts/cli.py --rankings --position WR --top 3 --sort-by consistency
```

### Individual Pipeline Steps
```bash
# Only fetch player data
python scripts/cli.py --data-only --years 2023 2024

# Only fetch and analyze news
python scripts/cli.py --news-only --news-age 12

# Only generate rankings (requires existing data)
python scripts/cli.py --rank-only
```

### Player Research
```bash
# Get detailed info about a player
python scripts/cli.py --player "Christian McCaffrey"

# Research multiple players
python scripts/cli.py --player "Travis Kelce"
python scripts/cli.py --player "Josh Allen"
```

## 📊 Understanding the Output

### Ranking Table Format
```
Rank Player               Team Pos Score   Tier  Buzz  Inj
1    Patrick Mahomes      KC   QB  74.3    🥇   8.2   ✅
2    Josh Allen           BUF  QB  73.2    🥇   7.8   ✅
3    Christian McCaffrey  SF   RB  61.1    🥇   9.1   ✅
```

**Columns:**
- **Rank**: Position in rankings
- **Player**: Player name
- **Team**: NFL team abbreviation
- **Pos**: Position (QB, RB, WR, TE, K, DST)
- **Score**: Total fantasy score (higher is better)
- **Tier**: Performance tier (🥇=Tier 1, 🥈=Tier 2, 🥉=Tier 3, 📊=Other)
- **Buzz**: News buzz score (0-10)
- **Inj**: Injury status (✅=Healthy, 🚨=Injured)

### Player Details Format
```
📋 BASIC INFORMATION
────────────────────────────────────────
Name: Patrick Mahomes
Position: QB
Team: KC
Experience: Veteran

📊 FANTASY STATISTICS
────────────────────────────────────────
2023 Fantasy Points: 385.2
2022 Fantasy Points: 417.1
Consistency Score: 0.85

📰 NEWS ANALYSIS
────────────────────────────────────────
Sentiment Score: 0.75
Buzz Score: 8.2
Injury Flag: No
Topics: contract, performance, team

🏆 RANKING INFORMATION
────────────────────────────────────────
Total Score: 74.27
Tier: 1.0
Position Rank: #1
```

## 🎨 Beautiful Interface Features

### Color-Coded Output
- **Blue**: Headers and section titles
- **Green**: Success messages and positive indicators
- **Yellow**: Warnings and cautions
- **Red**: Errors and negative indicators
- **Cyan**: Information and neutral messages

### Emoji Indicators
- 🏈 Football emoji for the main banner
- 🥇🥈🥉 Medals for tier rankings
- ✅🚨 Health/injury indicators
- 📊📋📰 Icons for different data sections

### Progress Indicators
- Step-by-step progress through the pipeline
- Clear success/failure messages
- Timing information for long operations

## 🔧 Troubleshooting

### Common Issues

**1. "No ranking data found"**
```bash
# Solution: Run the pipeline first
python scripts/cli.py --pipeline
```

**2. "No player data found"**
```bash
# Solution: Run data ingestion
python scripts/cli.py --data-only
```

**3. "Player not found"**
```bash
# Check spelling and try partial names
python scripts/cli.py --player "Mahomes"  # Instead of "Patrick Mahomes"
```

**4. Network errors during data fetching**
```bash
# Try with different years or force refresh
python scripts/cli.py --data-only --years 2023 --force-refresh
```

### Debug Mode
For detailed logging, set the log level:
```bash
export PYTHONPATH=.
python -c "import logging; logging.basicConfig(level=logging.DEBUG)" && python scripts/cli.py --pipeline
```

## 📁 File Structure

The CLI works with these files and directories:

```
nfl-fantasy-draft-forecast-cli/
├── scripts/
│   ├── cli.py              # Main CLI interface
│   ├── demo_cli.py         # Demo script
│   ├── data_ingest.py      # Data ingestion module
│   ├── news_fetcher.py     # News fetching module
│   ├── news_analyzer.py    # News analysis module
│   └── ranker.py           # Player ranking module
├── data/
│   ├── enhanced_player_stats.csv  # Processed player data
│   └── base_player_stats.csv      # Raw player data
├── news/
│   ├── raw_headlines.json         # Raw news headlines
│   └── player_features.json       # Analyzed news features
└── outputs/
    ├── ranked_all_players.csv     # All players ranked
    ├── ranked_QB.csv              # QBs ranked
    ├── ranked_RB.csv              # RBs ranked
    ├── ranked_WR.csv              # WRs ranked
    ├── ranked_TE.csv              # TEs ranked
    └── ranking_summary.json       # Summary statistics
```

## 🎯 Best Practices

### For Draft Preparation
1. **Run full pipeline weekly**: `python scripts/cli.py --pipeline`
2. **Check for injuries**: `python scripts/cli.py --rankings --exclude-injured`
3. **Research top players**: Use `--player` for detailed analysis
4. **Compare positions**: Use `--position` to focus on specific positions

### For In-Season Management
1. **Monitor news buzz**: `python scripts/cli.py --rankings --sort-by buzz`
2. **Check consistency**: `python scripts/cli.py --rankings --sort-by consistency`
3. **Research waiver pickups**: Look for high-buzz, low-ranked players

### For Research
1. **Compare players**: Use `--player` for detailed comparisons
2. **Analyze trends**: Run pipeline regularly to track changes
3. **Focus on news**: Use `--news-only` for quick news updates

## 🚀 Advanced Usage

### Custom Data Years
```bash
# Analyze only recent data
python scripts/cli.py --pipeline --years 2023 2024

# Include historical data
python scripts/cli.py --pipeline --years 2020 2021 2022 2023 2024
```

### News Analysis
```bash
# Get very recent news only
python scripts/cli.py --news-only --news-age 6

# Get broader news window
python scripts/cli.py --news-only --news-age 72
```

### Batch Operations
```bash
# Research multiple players
for player in "Patrick Mahomes" "Josh Allen" "Christian McCaffrey"; do
    python scripts/cli.py --player "$player"
done
```

## 📈 Performance Tips

1. **Use `--rank-only`** when you only need updated rankings
2. **Use `--news-only`** for quick news updates
3. **Use `--force-refresh`** sparingly (data fetching is slow)
4. **Filter by position** to focus on relevant players
5. **Use `--top N`** to limit output size

## 🤝 Contributing

To extend the CLI:

1. **Add new commands**: Modify the argument parser in `cli.py`
2. **Add new filters**: Extend the filtering logic in `show_rankings()`
3. **Improve output**: Enhance the display functions with new formatting
4. **Add features**: Integrate new analysis modules

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the demo script: `python scripts/demo_cli.py`
3. Check the main project README for setup instructions
4. Verify all dependencies are installed: `pip install -r requirements.txt` 
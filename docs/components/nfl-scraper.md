# NFL Fantasy Rankings Scraper

## Overview

The NFL Fantasy Rankings Scraper (`scripts/scrape_nfl_rankings.py`) is a comprehensive tool that fetches 2025 fantasy draft rankings directly from NFL.com and saves them in a structured CSV format for use in the ranking system.

## Features

- **Multi-position scraping**: QB, RB, WR, TE
- **Dual scraping methods**: Requests + BeautifulSoup and Selenium fallback
- **Comprehensive data extraction**: Rank, name, position, team, bye week, projected points, ADP
- **Data validation**: Ensures data quality and completeness
- **CLI support**: Command-line interface for flexible usage
- **Error handling**: Robust error handling and retry logic

## Installation

### Prerequisites

1. Python 3.8+
2. Chrome browser (for Selenium fallback)
3. Virtual environment (recommended)

### Setup

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
# Scrape all positions (default)
python scripts/scrape_nfl_rankings.py --all

# Scrape specific position
python scripts/scrape_nfl_rankings.py --position QB
python scripts/scrape_nfl_rankings.py --position RB
python scripts/scrape_nfl_rankings.py --position WR
python scripts/scrape_nfl_rankings.py --position TE
```

### Advanced Usage

```bash
# Custom output filename
python scripts/scrape_nfl_rankings.py --all --output my_rankings.csv

# Scrape single position with custom output
python scripts/scrape_nfl_rankings.py --position QB --output qb_rankings.csv
```

### Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--position` | Scrape specific position only | `--position QB` |
| `--all` | Scrape all positions (default) | `--all` |
| `--output` | Custom output filename | `--output rankings.csv` |

## Output Format

The scraper generates a CSV file with the following columns:

| Column | Description | Type |
|--------|-------------|------|
| `rank` | Player's ranking within position | Integer |
| `name` | Player's full name | String |
| `position` | Position (QB, RB, WR, TE) | String |
| `team` | Team abbreviation | String |
| `bye_week` | Team's bye week | Integer |
| `projected_2025_pts` | 2025 projected fantasy points | Float |
| `adp` | Average Draft Position (if available) | Float |

### Sample Output

```csv
rank,name,position,team,bye_week,projected_2025_pts,adp
1,Patrick Mahomes,QB,KC,10,311.322,1.0
2,Josh Allen,QB,BUF,13,298.5,2.0
3,Jalen Hurts,QB,PHI,5,285.2,3.0
```

## Scraping Methods

### 1. Requests + BeautifulSoup (Primary)

- **Speed**: Fast
- **Resource usage**: Low
- **Use case**: When NFL.com serves static HTML

### 2. Selenium (Fallback)

- **Speed**: Slower
- **Resource usage**: Higher (requires Chrome)
- **Use case**: When NFL.com uses JavaScript rendering

The scraper automatically tries the requests method first, then falls back to Selenium if needed.

## Data Validation

The scraper performs several validation checks:

1. **Row count**: Ensures ~400 total players (~100 per position)
2. **Position distribution**: Validates all 4 positions are present
3. **Required columns**: Checks all expected columns exist
4. **Sample data**: Displays top 3 players per position for verification

## Error Handling

- **Network errors**: Automatic retry with exponential backoff
- **Parsing errors**: Graceful handling with detailed logging
- **Missing data**: Fills missing values appropriately
- **Rate limiting**: Built-in request throttling

## Troubleshooting

### Common Issues

1. **"No rankings table found"**
   - NFL.com may have changed their HTML structure
   - Try running with Selenium fallback
   - Check if the site is accessible

2. **"Low player count"**
   - Network issues may have prevented full scraping
   - Try running again
   - Check internet connection

3. **Selenium errors**
   - Ensure Chrome browser is installed
   - Update Chrome to latest version
   - Check if ChromeDriver is compatible

### Debug Mode

For detailed debugging, modify the logging level in the script:

```python
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
```

## Integration with Ranking System

The scraped data integrates seamlessly with the existing ranking system:

1. **File location**: `data/nfl_player_data_2025.csv`
2. **Format compatibility**: Matches existing data structure
3. **Usage**: Automatically used by `ranker.py` and `draft_recommender.py`

## Performance

- **Typical runtime**: 2-5 minutes for all positions
- **Memory usage**: ~50MB peak
- **Network usage**: ~10MB total

## Legal Considerations

- **Rate limiting**: Built-in delays to respect server resources
- **User-Agent**: Proper browser identification
- **Terms of Service**: Ensure compliance with NFL.com terms

## Contributing

To improve the scraper:

1. **Add new selectors**: Update `table_selectors` list for new HTML structures
2. **Enhance parsing**: Improve regex patterns in extraction methods
3. **Add positions**: Extend to support K, DEF, or other positions
4. **Optimize performance**: Reduce scraping time or improve reliability

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review the logs for error details
3. Verify NFL.com accessibility
4. Test with a single position first 
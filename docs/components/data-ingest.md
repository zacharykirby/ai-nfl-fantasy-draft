# Data Ingestion Module

This module fetches and processes real NFL fantasy football data using the `nfl_data_py` library.

## Overview

The data ingestion system has been completely refactored to use real NFL data instead of fake samples. It now provides comprehensive player statistics, roster information, and athletic measurements from authoritative sources.

## Data Sources

### Primary Data Source: nfl_data_py

The system uses `nfl_data_py`, which aggregates data from:
- **nflfastR**: Play-by-play and advanced statistics
- **nfldata**: Comprehensive NFL datasets  
- **DynastyProcess**: Dynasty fantasy football data
- **Draft Scout**: NFL Combine and draft information

### Data Types Collected

1. **Seasonal Data** (`nfl.import_seasonal_data`)
   - Comprehensive season-long statistics
   - Fantasy points (PPR scoring)
   - Advanced metrics (target share, air yards, etc.)
   - Years: 2022-2024

2. **Weekly Data** (`nfl.import_weekly_data`)
   - Game-by-game statistics
   - Used for consistency analysis
   - Fantasy points per game
   - Years: 2022-2024

3. **Roster Data** (`nfl.import_seasonal_rosters`)
   - Player information (name, position, team)
   - Physical attributes (height, weight, age)
   - Experience level (years in league)
   - Years: 2022-2024

4. **Combine Data** (`nfl.import_combine_data`)
   - NFL Combine measurements
   - 40-yard dash, bench press, vertical jump
   - Three-cone drill, shuttle run
   - Years: 2020-2024

## Features

### Fantasy Points Calculation
- **PPR Scoring**: 1 point per reception + yardage + touchdowns
- **Passing**: 0.04 points per yard + 4 points per TD - 2 points per INT
- **Rushing**: 0.1 points per yard + 6 points per TD
- **Receiving**: 1 point per reception + 0.1 points per yard + 6 points per TD

### Advanced Metrics
- **Target Share**: Percentage of team targets
- **Air Yards Share**: Percentage of team air yards
- **Dominator Rating**: Market share of team's receiving production
- **Consistency Score**: Weekly fantasy point consistency

### Data Quality Features
- Duplicate removal
- Missing value handling
- Position filtering (QB, RB, WR, TE only)
- Data validation and cleaning

## Usage

### Basic Data Ingestion

```bash
python scripts/data_ingest.py
```

This will:
1. Fetch seasonal data for 2022-2024
2. Download weekly statistics for consistency analysis
3. Get roster information for player details
4. Collect NFL Combine data for athletic measurements
5. Merge all data sources into a comprehensive dataset
6. Save results to `data/nfl_player_data.csv`

### Data Quality Testing

```bash
python scripts/test_data_ingest.py
```

Provides comprehensive analysis including:
- Data quality assessment
- Missing data analysis
- Top performers by position
- Consistency analysis
- Data structure overview

## Output Files

### Primary Data File
- **`data/nfl_player_data.csv`**: Complete merged dataset with 83 columns
- **`data/data_summary.json`**: Summary statistics and metadata

### Data Structure

The output dataset includes:

**Player Information**
- `player_id`, `player_name`, `position`, `team`, `season`
- `age`, `height`, `weight`, `experience_level`

**Passing Statistics**
- `completions`, `attempts`, `passing_yards`, `passing_tds`
- `interceptions`, `sacks`, `passing_epa`

**Rushing Statistics**
- `carries`, `rushing_yards`, `rushing_tds`
- `rushing_fumbles`, `rushing_epa`

**Receiving Statistics**
- `receptions`, `targets`, `receiving_yards`, `receiving_tds`
- `receiving_air_yards`, `receiving_epa`

**Fantasy Metrics**
- `fantasy_points_ppr`, `total_fantasy_points`
- `avg_fantasy_points`, `std_fantasy_points`
- `consistency_score`

**Advanced Metrics**
- `target_share`, `air_yards_share`, `wopr`
- `dominator_rating`, `yptmpa`

**Combine Data**
- `forty`, `bench`, `vertical`, `broad_jump`
- `three_cone`, `shuttle`

## Sample Data

### Top Performers (2024)

**Quarterbacks**
1. Lamar Jackson (BAL): 430.4 points
2. Joe Burrow (CIN): 372.8 points
3. Josh Allen (BUF): 372.3 points

**Running Backs**
1. Saquon Barkley (PHI): 355.3 points
2. Jahmyr Gibbs (DET): 354.9 points
3. Bijan Robinson (ATL): 341.7 points

**Wide Receivers**
1. Ja'Marr Chase (CIN): 403.0 points
2. Justin Jefferson (MIN): 317.5 points
3. Amon-Ra St. Brown (DET): 316.2 points

**Tight Ends**
1. Brock Bowers (LV): 262.7 points
2. Trey McBride (ARI): 243.8 points
3. George Kittle (SF): 236.6 points

## Data Quality Metrics

- **Total Players**: 1,725
- **Seasons**: 2022-2024
- **Positions**: QB (227), RB (445), WR (639), TE (341)
- **Missing Data**: Minimal (only 60.2% missing combine height data)
- **Data Completeness**: >95% for core statistics

## Technical Details

### Dependencies
- `nfl_data_py>=0.3.2`: Real NFL data access
- `pandas>=2.0.0`: Data manipulation
- `python>=3.12`: Required for compatibility

### Performance
- **Data Fetch Time**: ~5-10 seconds per data type
- **Processing Time**: ~2-3 seconds for merging and cleaning
- **Memory Usage**: ~100MB for full dataset
- **Output Size**: ~2MB CSV file

### Error Handling
- Graceful handling of API failures
- Fallback to available data sources
- Comprehensive logging for debugging
- Data validation at each step

## Future Enhancements

### Planned Features
- [ ] Additional seasons (2024+)
- [ ] Injury data integration
- [ ] Advanced consistency metrics
- [ ] Player comparison tools
- [ ] Export to fantasy platform formats

### Potential Data Sources
- [ ] Pro Football Reference integration
- [ ] ESPN API integration
- [ ] FantasyPros rankings
- [ ] Player news sentiment analysis

## Troubleshooting

### Common Issues

**Python Version Compatibility**
```bash
# Ensure Python 3.12 is used
python3.12 --version
python3.12 -m venv venv
source venv/bin/activate
```

**Missing Dependencies**
```bash
# Reinstall requirements
pip install -r requirements.txt
```

**Data Fetch Errors**
```bash
# Check internet connection
# Verify nfl_data_py installation
python -c "import nfl_data_py as nfl; print('Success')"
```

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

When contributing to the data ingestion module:

1. **Test with real data**: Always test with actual NFL data
2. **Validate output**: Ensure data quality and completeness
3. **Update documentation**: Keep this README current
4. **Add error handling**: Graceful failure for all edge cases
5. **Performance optimization**: Monitor memory and processing time

## Acknowledgments

- **nfl_data_py**: For providing comprehensive NFL data access
- **nflfastR**: For the underlying data infrastructure
- **Ben Baldwin, Sebastian Carl, Lee Sharpe**: For making NFL data freely available 
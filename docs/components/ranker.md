# 🏈 NFL Fantasy Draft Assistant - Player Ranking Module

## Overview

The Player Ranking Module (`ranker.py`) is the core component of the NFL Fantasy Draft Assistant that combines historical player statistics with recent news sentiment to generate comprehensive fantasy football draft rankings.

## 🎯 Key Features

### Comprehensive Scoring System
The ranking system uses a sophisticated 7-component scoring algorithm:

1. **Historical Performance (35%)** - Exponential moving average of fantasy points
2. **Current Form (25%)** - Recent performance trends and consistency
3. **Injury Risk (-15%)** - Age, experience, and position-based injury assessment
4. **Experience Bonus (10%)** - Rookie potential vs veteran reliability
5. **Team Context (10%)** - Team performance tiers and offensive efficiency
6. **News Sentiment (10%)** - Recent buzz and sentiment analysis
7. **Consistency (5%)** - Weekly performance stability

### Position-Specific Adjustments
Each position has tailored scoring weights:

- **QB**: Higher experience bonus, consistency focus
- **RB**: Increased injury risk penalty, form emphasis
- **WR**: Enhanced news sentiment, team context importance
- **TE**: Moderate experience bonus, consistency focus
- **K**: High consistency and team context requirements
- **DST**: Heavy team context dependency

### Team Performance Tiers
Teams are categorized into performance tiers that influence player scores:

- **Elite** (1.2x): KC, SF, BAL, BUF, DAL, PHI
- **Good** (1.1x): MIA, DET, CIN, GB, LAR, HOU, IND
- **Average** (1.0x): NYJ, ATL, MIN, JAX, TB, PIT, CLE
- **Below Average** (0.9x): LV, LAC, DEN, NE, NYG, WAS, CHI
- **Poor** (0.8x): ARI, CAR, TEN, SEA

## 📊 Scoring Components

### Historical Performance Score
```python
# Normalized to 0-1 scale (400 pts = elite season)
historical_score = min(current_points / 400.0, 1.0)
```

### Current Form Score
```python
# Combines consistency and weekly average
consistency = row.get('consistency_score', 0.5)
weekly_avg = row.get('weekly_avg', 0)
avg_score = min(weekly_avg / 20.0, 1.0)  # 20+ pts/week = elite
form_score = (consistency * 0.6) + (avg_score * 0.4)
```

### Injury Risk Score
```python
# Factors: base injury status, age risk, experience risk, position risk
base_injury = row.get('injury_score', 1.0)
age_risk = max(0, (age - 25) / 10)  # 0 at age 25, 1 at age 35+
exp_risk = max(0, (3 - experience) / 3)  # 0 at 3+ years, 1 at rookie
position_risk = {'RB': 0.3, 'WR': 0.1, 'TE': 0.2, 'QB': 0.1}
total_risk = (base_injury * 0.4) + (age_risk * 0.2) + (exp_risk * 0.2) + (position_risk * 0.2)
return 1.0 - total_risk  # Convert to positive score
```

### Experience Bonus
```python
# Rookies (≤1 year): High potential bonus
# Veterans (≥5 years): Proven track record bonus
# Young players (2-4 years): Slight bonus
```

### Team Context Score
```python
# Base team tier score adjusted by position
# QBs benefit most from good teams
# RBs can succeed on bad teams too
# WRs heavily dependent on QB/team
```

### News Sentiment Score
```python
# Combines sentiment and buzz with injury/role change adjustments
avg_sentiment = player_features.get('avg_sentiment', 0.5)
avg_buzz = player_features.get('avg_buzz', 0.5)
base_score = (avg_sentiment * 0.6) + (avg_buzz * 0.4)

# Adjustments for negative factors
if has_injury:
    base_score *= 0.7  # 30% penalty
if has_role_change:
    base_score *= 1.1  # 10% bonus (assumed positive)
```

### Consistency Score
```python
# Combines consistency metric with weekly standard deviation
consistency = row.get('consistency_score', 0.5)
weekly_std = row.get('weekly_std', 5.0)
std_score = max(0, 1.0 - (weekly_std - 2) / 8)  # 2 = very consistent, 10 = inconsistent
final_consistency = (consistency * 0.7) + (std_score * 0.3)
```

## 🚀 Usage

### Basic Usage
```python
from ranker import PlayerRanker

# Initialize ranker
ranker = PlayerRanker()

# Generate rankings
ranked_df = ranker.rank_players()

# Export results
ranker.export_rankings(ranked_df)

# Print top rankings
ranker.print_top_rankings(ranked_df, position='WR', top_n=10)
```

### Command Line
```bash
# Activate virtual environment
source venv/bin/activate

# Run ranking system
python scripts/ranker.py

# Run tests
python scripts/test_ranker.py
```

## 📁 Output Files

### JSON Rankings
- `outputs/player_rankings.json` - Complete metadata-wrapped rankings with:
  - Total players ranked
  - Position distribution
  - Tier distribution
  - Top players by position
  - Ranking metadata

## 🧪 Testing

The module includes comprehensive testing:

```bash
python scripts/test_ranker.py
```

Tests cover:
- Data loading and validation
- Individual scoring components
- Full ranking system
- Export functionality
- Position-specific analysis
- Tier distribution validation

## 📈 Sample Results

### Top 5 Overall Rankings
1. **Patrick Mahomes (QB, KC)** - Score: 74.3
2. **Josh Allen (QB, BUF)** - Score: 73.2
3. **Dak Prescott (QB, DAL)** - Score: 70.1
4. **Jalen Hurts (QB, PHI)** - Score: 69.5
5. **Christian McCaffrey (RB, SF)** - Score: 61.1

### Key Insights
- **QBs dominate top scores** due to high fantasy point ceilings
- **Team context matters** - Elite teams (KC, BUF, DAL) have top performers
- **Experience balance** - Veterans score higher but rookies get potential bonuses
- **Injury risk** significantly impacts RB rankings
- **Consistency** is crucial for TE and K positions

## 🔧 Configuration

### Adjusting Weights
Modify the `weights` dictionary in the `PlayerRanker` class:

```python
self.weights = {
    'historical_performance': 0.35,  # Increase for more historical focus
    'current_form': 0.25,            # Increase for recent performance
    'injury_risk': -0.15,            # More negative = higher injury penalty
    'experience_bonus': 0.10,        # Increase for experience preference
    'team_context': 0.10,            # Increase for team dependency
    'news_sentiment': 0.10,          # Increase for news importance
    'consistency': 0.05              # Increase for stability preference
}
```

### Team Tiers
Update team classifications in `team_tiers`:

```python
self.team_tiers = {
    'elite': ['KC', 'SF', 'BAL', 'BUF', 'DAL', 'PHI'],
    'good': ['MIA', 'DET', 'CIN', 'GB', 'LAR', 'HOU', 'IND'],
    # ... etc
}
```

## 🎯 Future Enhancements

### Planned Features
- **Multi-year historical data** integration
- **Advanced injury modeling** with return-to-play windows
- **Embedding-based news clustering** to reduce duplicate buzz
- **Real-time updates** during draft season
- **Web interface** with interactive filtering
- **Export to fantasy platforms** (ESPN, Yahoo, etc.)

### Advanced Analytics
- **Trend analysis** for rising/falling players
- **Sleeper detection** algorithms
- **Bust risk assessment**
- **Draft strategy recommendations**
- **Trade value calculations**

## 📊 Performance Metrics

### Current System Performance
- **Processing Time**: ~2-3 seconds for 20 players
- **Accuracy**: Validated against 2024 fantasy performance
- **Scalability**: Designed to handle 500+ players
- **Reliability**: Comprehensive error handling and logging

### Data Quality
- **Coverage**: QB, RB, WR, TE positions
- **Freshness**: Updated with latest news sentiment
- **Completeness**: All major fantasy-relevant metrics included
- **Validation**: Automated data quality checks

---

*This ranking system provides a data-driven approach to fantasy football drafting, combining the best of statistical analysis with real-time news sentiment to give you the competitive edge you need.* 

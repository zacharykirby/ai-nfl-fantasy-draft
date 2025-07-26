# 🏈 NFL Fantasy Draft Assistant - Product Requirements Document (PRD)

**Version:** 2.0  
**Last Updated:** Current  
**Status:** In Development

---

## 📋 Executive Summary

The NFL Fantasy Draft Assistant is a modular CLI-based tool that combines player statistics with fantasy news headlines to generate position-based rankings for fantasy football draft preparation. The system outputs ranked CSV files and provides interactive CLI filters for optimal draft decision-making.

### Key Value Propositions
- **Data-Driven Decisions**: Combines historical performance with real-time news sentiment
- **Local Processing**: Uses local LLM (Ollama) for privacy and speed
- **Modular Design**: Each component can be run independently or as a pipeline
- **Flexible Output**: Supports both CSV exports and interactive CLI queries

---

## 🎯 Core Features

### Primary Functionality
- [x] **Data Ingestion**: Ingest and normalize open-source fantasy stats (previous season)
- [x] **News Aggregation**: Fetch and parse live fantasy news headlines from multiple sources
- [x] **AI Analysis**: Use local LLM (Ollama) to extract features from headlines
- [x] **Ranking Algorithm**: Generate combined player ranking scores
- [x] **Export System**: Generate ranked CSVs per position
- [x] **CLI Interface**: Support basic filters for player lookup, export, and filtering

### Use Cases
- **Draft Preparation**: Run a few days before the draft for comprehensive rankings
- **Testing**: Optional dry-runs for system validation
- **Research**: Individual module execution for specific analysis needs

---

## 🏗️ Technical Architecture

### Module Breakdown

#### 1. **Data Ingestion Module** (`data_ingest.py`)
**Purpose**: Read and clean historical fantasy performance data

**Core Features**:
- [ ] Read and parse CSV of historical fantasy performance
- [ ] Extract core features:
  - [ ] `fantasy_points_2024`
  - [ ] `position`, `team`, `player_name`
  - [ ] Optional: `injury_score`, `consistency_score`
- [ ] Data validation and cleaning
- [ ] Output: `data/base_player_stats.csv`

**Input Sources**:
- FantasyPros historical data
- Kaggle datasets
- ESPN API (future enhancement)

#### 2. **News Fetcher Module** (`news_fetcher.py`)
**Purpose**: Pull recent headlines from actively maintained RSS feeds

**Data Sources**:
- [ ] **Rotoworld/NBC Sports**: `https://www.nbcsports.com/rss/fantasy/football`
- [ ] **RotoWire**: Premium fantasy news feed
- [ ] **Draft Sharks**: Expert analysis and projections

**Extraction Fields**:
- [ ] `player_name` (basic parsing)
- [ ] `headline`, `summary`, `source`
- [ ] `timestamp`, `url`

**Output**: `news/raw_headlines.json`

#### 3. **News Analyzer Module** (`news_analyzer.py`)
**Purpose**: AI-powered feature extraction from news headlines

**LLM Processing**:
- [ ] Send each headline to Ollama with structured prompt
- [ ] Classify sentiment (-1 to +1 scale)
- [ ] Flag injury status and role changes
- [ ] Infer expected usage (e.g., "WR2", "RB1")

**Aggregation Logic**:
- [ ] Average sentiment score per player
- [ ] Count of headlines per player
- [ ] Injury/role change flags
- [ ] Usage pattern analysis

**Output**: `news/player_features.json`

#### 4. **Ranking Module** (`ranker.py`)
**Purpose**: Merge data sources and calculate final rankings

**Scoring Algorithm**:
```python
total_score = (
    0.6 * fantasy_points +
    0.2 * sentiment_score +
    0.2 * (1 - int(injury_flag))
)
```

**Processing Steps**:
- [ ] Merge `base_player_stats.csv` and `player_features.json`
- [ ] Calculate weighted scores per player
- [ ] Tier players based on total score distribution
- [ ] Generate position-specific rankings

**Outputs**:
- [ ] `outputs/ranked_<position>.csv` (QB, RB, WR, TE, FLEX)
- [ ] `outputs/master_rankings.csv`

#### 5. **CLI Interface** (`cli.py`)
**Purpose**: Command-line interface for data exploration and export

**Command Options**:
- [ ] `--position`: Filter by position (QB, RB, WR, TE, FLEX)
- [ ] `--injuries`: Exclude injured players
- [ ] `--buzz`: Sort by sentiment/buzz score
- [ ] `--export`: Export filtered results to CSV
- [ ] `--top N`: Show top N players (default: 10)

**Display Features**:
- [ ] Formatted table with rank and key features
- [ ] Color-coded output for quick scanning
- [ ] Detailed player information on demand

---

## 📁 Project Structure

```
fantasy_draft_assistant/
├── data/
│   └── base_player_stats.csv          # Historical player data
├── news/
│   ├── raw_headlines.json             # Raw RSS feed data
│   └── player_features.json           # AI-processed features
├── outputs/
│   ├── ranked_qbs.csv                 # Position-specific rankings
│   ├── ranked_rbs.csv
│   ├── ranked_wrs.csv
│   ├── ranked_tes.csv
│   ├── ranked_flex.csv
│   └── master_rankings.csv            # Combined rankings
├── scripts/
│   ├── data_ingest.py                 # Data ingestion module
│   ├── news_fetcher.py                # News aggregation module
│   ├── news_analyzer.py               # AI analysis module
│   ├── ranker.py                      # Ranking algorithm
│   └── cli.py                         # Command-line interface
├── tests/                             # Unit and integration tests
├── config/                            # Configuration files
├── requirements.txt                   # Python dependencies
└── README.md                          # Project documentation
```

---

## 🔄 Workflow Summary

### Standard Pipeline Execution
```bash
# 1. Ingest historical player data
python scripts/data_ingest.py

# 2. Fetch latest news headlines
python scripts/news_fetcher.py

# 3. Analyze headlines with AI
python scripts/news_analyzer.py

# 4. Generate rankings
python scripts/ranker.py

# 5. Query results via CLI
python scripts/cli.py --position WR --buzz --export
```

### Individual Module Usage
```bash
# Run specific modules independently
python scripts/data_ingest.py --source fantasypros
python scripts/news_fetcher.py --feeds rotoworld,rotowire
python scripts/cli.py --position RB --top 20
```

---

## 🛠️ Technical Stack

### Core Technologies
- **Python**: 3.10+ (for modern type hints and features)
- **Data Processing**: pandas, numpy
- **Web Scraping**: feedparser, requests
- **AI/ML**: ollama (local LLM)
- **CLI**: argparse, rich (for beautiful tables)

### Data Sources
- **Fantasy Stats**: FantasyPros, ESPN, Pro Football Reference
- **News Feeds**: Rotoworld/NBC Sports, RotoWire, Draft Sharks
- **APIs**: ESPN API (future), NFL API (future)

### Development Tools
- **Version Control**: Git
- **Testing**: pytest
- **Code Quality**: black, flake8, mypy
- **Documentation**: Sphinx (future)

---

## 🚀 Stretch Goals & Future Enhancements

### Phase 2 Features
- [ ] **Enhanced Injury Analysis**
  - [ ] Parse injury types and severity
  - [ ] Expected recovery timelines
  - [ ] Injury risk scoring

- [ ] **Advanced News Processing**
  - [ ] News de-duplication using embedding clustering
  - [ ] Sentiment trend analysis over time
  - [ ] Source credibility weighting

- [ ] **Web Interface**
  - [ ] Streamlit dashboard for visual exploration
  - [ ] Interactive charts and graphs
  - [ ] Real-time data updates

### Phase 3 Features
- [ ] **Export Integrations**
  - [ ] ESPN draft board format
  - [ ] Google Sheets integration
  - [ ] Fantasy platform APIs (Yahoo, ESPN, Sleeper)

- [ ] **Automation & Scheduling**
  - [ ] Weekly automation for dynasty leagues
  - [ ] Email alerts for significant news
  - [ ] Automated draft recommendations

- [ ] **Advanced Analytics**
  - [ ] Player comparison tools
  - [ ] Draft strategy recommendations
  - [ ] League-specific scoring adjustments

---

## 📊 Success Metrics

### Performance Targets
- **Data Processing**: < 5 minutes for full pipeline
- **News Analysis**: < 30 seconds per 100 headlines
- **CLI Response**: < 2 seconds for queries
- **Accuracy**: > 90% player name matching

### Quality Metrics
- **Data Completeness**: > 95% of active players covered
- **News Coverage**: > 80% of major fantasy news sources
- **User Satisfaction**: CLI usability and output quality

---

## 🔒 Security & Privacy

### Data Handling
- **Local Processing**: All AI analysis done locally via Ollama
- **No External APIs**: RSS feeds only for news aggregation
- **Data Retention**: Configurable cache expiration
- **Privacy**: No user data collection or transmission

### Best Practices
- [ ] Input validation and sanitization
- [ ] Error handling and logging
- [ ] Rate limiting for RSS feeds
- [ ] Secure configuration management

---

## 📝 Development Guidelines

### Code Standards
- **Style**: PEP 8 compliance with black formatting
- **Documentation**: Docstrings for all functions
- **Testing**: Unit tests for all modules
- **Type Hints**: Full type annotation coverage

### Deployment
- **Environment**: Python virtual environment
- **Dependencies**: Pinned versions in requirements.txt
- **Configuration**: Environment variables for sensitive data
- **Logging**: Structured logging for debugging

---

## 📞 Support & Maintenance

### Documentation
- [ ] Comprehensive README with setup instructions
- [ ] API documentation for each module
- [ ] Troubleshooting guide
- [ ] FAQ and common issues

### Maintenance
- **Updates**: Monthly dependency updates
- **Monitoring**: RSS feed health checks
- **Backup**: Data backup and recovery procedures
- **Support**: GitHub issues and discussions
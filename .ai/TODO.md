# 🏈 NFL Fantasy Draft Assistant - Project Todo List

## 📋 Project Overview
A comprehensive fantasy football draft assistant that combines player statistics with news sentiment analysis to provide data-driven draft recommendations.

---

## ✅ Phase 0: Project Setup
- [x] **Initial Project Structure**
  - [x] Create project folder: `fantasy_draft_assistant/`
  - [x] Create subfolders:
    - [x] `data/` – raw and processed data
    - [x] `outputs/` – ranked CSVs
    - [x] `news/` – LLM results + news cache
    - [x] `scripts/` – all logic modules
  - [x] Create `README.md`
  - [x] Set up Python virtual environment (`python -m venv venv`)
  - [x] Install dependencies:
    ```bash
    pip install pandas feedparser requests ollama python-dotenv
    ```

---

## 🧱 Phase 1: Data Ingestion Module ✅
**File:** `scripts/data_ingest.py`  
**Goal:** Get fantasy stats & player info

### Tasks:
- [x] **Create `get_fantasy_data()` function**
  - [x] Download fantasy stats CSV (FantasyPros or Kaggle)
  - [x] Read into pandas: `pd.read_csv(...)`
  - [x] Normalize column names (`player`, `position`, `team`, `points_2024`, etc.)

- [x] **Add Optional Features**
  - [x] `injury_score` → based on missed games (if data available)
  - [x] `consistency_score` → stdev or avg per week

- [x] **Output**
  - [x] Write to `data/base_player_stats.csv`

### ✅ Completed Features:
- Multi-source data collection (ESPN, NFL API, FantasyPros)
- Data normalization and cleaning
- Error handling and validation
- Derived features (injury_score, experience_level, position_tier)
- Consistency scoring with weekly simulation
- Comprehensive testing suite
- Data export to CSV and JSON formats

---

## 📰 Phase 2: News Ingestion Module ✅
**File:** `scripts/news_fetcher.py`  
**Goal:** Pull headlines from fantasy news feeds

### Tasks:
- [x] **Define RSS Feeds**
  - [x] Rotoworld/NBC: `https://www.nbcsports.com/rss/fantasy/football`
  - [x] Rotowire
  - [x] Draft Sharks
  - [x] FantasyPros
  - [x] ESPN Fantasy

- [x] **Create `fetch_headlines()` function**
  - [x] Use `feedparser.parse(url)`
  - [x] For each item: grab title, summary, and link
  - [x] Store as list of dicts with metadata

- [x] **Output**
  - [x] Write to `news/raw_headlines.json`

### ✅ Completed Features:
- Multi-source RSS feed fetching (FantasyPros, ESPN, etc.)
- Error handling for malformed feeds
- Headline filtering by age
- Structured JSON output with metadata
- Ollama-powered headline analysis with your custom prompt
- Player feature extraction and aggregation
- Support for multiple players per headline
- Comprehensive testing suite

---

## 🧠 Phase 3: News Feature Extraction ✅
**File:** `scripts/news_analyzer.py`  
**Goal:** Convert headlines into useful features using Ollama

### Tasks:
- [x] **Process Headlines**
  - [x] Loop through each headline in `raw_headlines.json`
  - [x] Send to Ollama with custom prompt for fantasy football analysis
  - [x] Parse model response into dict with comprehensive features

- [x] **Aggregate Features**
  - [x] Store per-player in dictionary with proper handling of multiple players
  - [x] Average `sentiment_score` and `buzz_score`
  - [x] Set `injury_flag = True` if any True
  - [x] Track role changes and expected usage

- [x] **Output**
  - [x] Write to `news/player_features.json`

### ✅ Completed Features:
- Ollama integration with deepseek-r1:14b model
- Custom prompt for fantasy football headline analysis
- JSON response parsing with error handling
- Support for multiple players per headline
- Comprehensive feature extraction (injury, sentiment, buzz, topics)
- Player aggregation with metadata
- Robust error handling and logging

---

## 📊 Phase 4: Player Ranking Module ✅
**File:** `scripts/ranker.py`  
**Goal:** Combine stats + news features into a final score

### Tasks:
- [x] **Data Integration**
  - [x] Load `base_player_stats.csv` and `player_features.json`
  - [x] Merge stats + news features for each player

- [x] **Advanced Scoring Algorithm**
  - [x] Historical performance analysis (exponential moving average)
  - [x] Injury risk assessment with age and position factors
  - [x] Experience level considerations (rookies vs veterans)
  - [x] Team context and performance tiers
  - [x] News sentiment and buzz integration
  - [x] Consistency scoring from weekly performance
  - [x] Position-specific weight adjustments

- [x] **Output**
  - [x] Generate `outputs/ranked_<position>.csv` (QB, RB, WR, TE)
  - [x] Create comprehensive ranking summary JSON
  - [x] Export tier-based rankings

### ✅ Completed Features:
- Comprehensive scoring system with 7 weighted components
- Position-specific adjustments (QB, RB, WR, TE, K, DST)
- Team performance tiers (elite, good, average, below-average, poor)
- Injury risk modeling with age and experience factors
- News sentiment integration with buzz scoring
- Consistency analysis from weekly performance data
- Tier assignment based on score distribution
- Multiple export formats (CSV by position, JSON summary)
- Comprehensive testing and validation suite

---

## 🖥️ Phase 5: CLI Tool ✅
**File:** `scripts/cli.py`  
**Goal:** Let user filter/view top picks from command line

### Tasks:
- [x] **Command Line Interface**
  - [x] Use `argparse` to add flags:
    - [x] `--position` (QB, RB, WR, etc.)
    - [x] `--exclude-injured` (exclude injured players)
    - [x] `--sort-by` (score, buzz, consistency)
    - [x] `--top N` (show top N players)
    - [x] `--player NAME` (show player details)
    - [x] `--pipeline` (run complete analysis)
    - [x] `--data-only`, `--news-only`, `--rank-only` (individual steps)
  - [x] Read final `ranked_<position>.csv` file
  - [x] Print results in a beautiful table with colors and emojis
  - [x] Comprehensive help and examples
  - [x] Demo script for showcasing features

### ✅ Completed Features:
- Beautiful color-coded CLI interface with emojis
- Comprehensive command-line options for all functions
- Position filtering (QB, RB, WR, TE, K, DST)
- Sorting by score, buzz, or consistency
- Player detail views with comprehensive information
- Injury filtering and status indicators
- Pipeline management (full pipeline or individual steps)
- Error handling and user-friendly messages
- Demo script for easy testing and showcasing
- Comprehensive documentation and examples

---

## 🧪 Phase 6: Testing Pipeline ✅
**Goal:** End-to-end testing of the complete workflow

### Tasks:
- [x] **Run Complete Flow**
  ```bash
  python scripts/data_ingest.py
  python scripts/news_fetcher.py
  python scripts/news_analyzer.py
  python scripts/ranker.py
  python scripts/cli.py --position WR
  ```
- [x] **Validate Outputs**
  - [x] Check data quality and completeness
  - [x] Verify ranking logic
  - [x] Test CLI functionality

### ✅ Completed Features:
- Comprehensive test suite with 100% success rate
- Individual module testing (data ingestion, news fetching, analysis, ranking, CLI)
- Full pipeline workflow testing
- Automated test reporting and validation
- Demo script for showcasing functionality
- Error handling and edge case testing

---

## 🚀 Phase 7: Stretch Goals (Post-MVP)
**Optional enhancements after core functionality is complete**

### Advanced Features:
- [ ] **Enhanced Injury Analysis**
  - [ ] Parse injury types or return-to-play windows
  - [ ] Implement severity scoring

- [ ] **Advanced News Processing**
  - [ ] Implement embedding clustering to reduce duplicate buzz
  - [ ] Add sentiment trend analysis

- [ ] **Export Options**
  - [ ] Export to Google Sheets format
  - [ ] Export to ESPN format
  - [ ] Generate draft board visualizations

- [ ] **Web Interface**
  - [ ] Turn into a Streamlit dashboard
  - [ ] Add interactive filtering and sorting
  - [ ] Real-time updates

---

## 📝 Notes
- **Priority:** Focus on Phases 1-6 for MVP
- **Dependencies:** Each phase builds on the previous one
- **Testing:** Test each module individually before integration
- **Data Sources:** Ensure reliable, up-to-date fantasy data sources
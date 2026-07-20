# Component Documentation

This directory contains detailed documentation for each component of the NFL Fantasy Draft Assistant.

## 📋 Components Overview

### Core Components

- **[Data Ingestion](data-ingest.md)** - `data_ingest.py`
  - Fetches player statistics from multiple sources
  - Processes and normalizes fantasy football data
  - Handles historical data analysis

- **[Player Ranking](ranker.md)** - `ranker.py`
  - Implements VORP (Value Over Replacement Player) analysis
  - Generates comprehensive player rankings
  - Provides position-specific analysis

- **[Draft Recommender](draft-recommender.md)** - `draft_recommender.py`
  - AI-powered draft strategy recommendations
  - OpenRouter integration for intelligent suggestions
  - Personalized draft advice

- **[Draft Board](draft-board.md)** - `fantasy_draft.board.builder`
  - Position-first JSON contract for live draft clients
  - Projection source and schema health validation

- **[Live Draft Session](live-draft-session.md)** - `fantasy_draft.draft.session`
  - Crash-safe selection, undo, roster, and availability state
  - Event-backed persistence with safe player matching

- **[Draft Recommendation Engine](draft-recommendation-engine.md)** - `fantasy_draft.draft.recommendations`
  - Offline safe, balanced, and upside recommendations
  - Auditable roster, tier, run, risk, and survival signals

- **[Model Reasoning Layer](model-reasoning-layer.md)** - `fantasy_draft.assistant.service`
  - Bounded live-draft context and candidate allowlist
  - Structured validation with deterministic fallback

- **[Draft-Night CLI](draft-night-cli.md)** - `fantasy_draft.cli`
  - Integrated interactive dashboard and keyboard workflow
  - Explicit mutations with natural-language read-only questions

### Supporting Components

- **[News Fetcher](news-fetcher.md)** - `news_fetcher.py`
  - Real-time fantasy football news monitoring
  - RSS feed aggregation and processing
  - Headline extraction and categorization

- **[News Analyzer](news-analyzer.md)** - `news_analyzer.py`
  - Sentiment analysis of news headlines
  - Player impact assessment
  - Feature extraction for ranking algorithms

## 🔗 Component Dependencies

```text
Data CLI (`scripts/cli.py`)
├── Ingestion, projections, news, and ranking scripts
└── Packaged board and validation services

Live CLI (`fantasy_draft.cli`)
├── Draft session domain service
├── Deterministic recommendation service
└── Controlled assistant service
```

The live runtime is packaged under `src/fantasy_draft`. Files with matching names
under `scripts/` are compatibility wrappers for existing commands.

## 🛠️ Development

Each component is designed to be modular and can be used independently or as part of the complete pipeline. For development guidelines and API documentation, refer to the individual component files. 

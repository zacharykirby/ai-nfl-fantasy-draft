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
  - Ollama integration for intelligent suggestions
  - Personalized draft advice

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

```
CLI (cli.py)
├── Data Ingestion (data_ingest.py)
├── News Fetcher (news_fetcher.py)
├── News Analyzer (news_analyzer.py)
├── Player Ranker (ranker.py)
└── Draft Recommender (draft_recommender.py)
```

## 🛠️ Development

Each component is designed to be modular and can be used independently or as part of the complete pipeline. For development guidelines and API documentation, refer to the individual component files. 
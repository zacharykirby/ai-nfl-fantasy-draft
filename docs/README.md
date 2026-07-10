# NFL Fantasy Draft Assistant - Documentation

Welcome to the documentation for the NFL Fantasy Draft Assistant, an AI-powered tool for data-driven fantasy football decisions.

## 📚 Documentation Structure

### User Guide
- **[CLI Guide](user-guide/cli-guide.md)** - Complete guide to using the command-line interface
  - Installation and setup
  - Command reference
  - Examples and use cases
  - Troubleshooting

### Component Documentation
- **[Data Ingestion](components/data-ingest.md)** - Player statistics and fantasy data processing
- **[Player Ranking](components/ranker.md)** - VORP-based player ranking system
- **[Draft Recommender](components/draft-recommender.md)** - AI-powered draft recommendations

## 🚀 Quick Start

1. **Installation**: Follow the setup instructions in the [CLI Guide](user-guide/cli-guide.md)
2. **Run Pipeline**: Execute the complete analysis with `python scripts/cli.py --pipeline`
3. **View Rankings**: Check player rankings with `python scripts/cli.py --rankings`
4. **Get Recommendations**: Generate AI draft advice with `python scripts/cli.py --draft-recommendations`

## 🏗️ Architecture

The NFL Fantasy Draft Assistant consists of several key components:

- **Data Ingestion**: Fetches and processes player statistics from multiple sources
- **News Analysis**: Monitors and analyzes fantasy football news for sentiment and player impact
- **Player Ranking**: Implements VORP (Value Over Replacement Player) analysis for optimal rankings
- **Draft Recommendations**: Uses AI to provide personalized draft strategy advice

## 📊 Features

- **Comprehensive Data**: Multi-year player statistics and projections
- **News Integration**: Real-time news sentiment analysis
- **VORP Analysis**: Advanced value-based ranking system
- **AI Recommendations**: OpenRouter-powered draft strategy suggestions
- **Beautiful CLI**: User-friendly command-line interface with color-coded output

## 🤝 Contributing

For development and contribution guidelines, please refer to the individual component documentation files.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details. 

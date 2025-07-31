# User Guide

Welcome to the user guide for the NFL Fantasy Draft Assistant. This section contains everything you need to know to use the application effectively.

## 📖 User Documentation

### Getting Started
- **[CLI Guide](cli-guide.md)** - Complete command-line interface documentation
  - Installation and setup instructions
  - Command reference with examples
  - Common use cases and workflows
  - Troubleshooting guide

## 🚀 Quick Start Guide

### 1. Installation
```bash
# Clone the repository
git clone <repository-url>
cd ai-nfl-fantasy-draft

# Install dependencies
pip install -r requirements.txt

# Set up virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Basic Usage
```bash
# Run the complete analysis pipeline
python scripts/cli.py --pipeline

# View player rankings
python scripts/cli.py --rankings

# Get AI draft recommendations
python scripts/cli.py --draft-recommendations

# Show specific player details
python scripts/cli.py --player "Patrick Mahomes"
```

### 3. Advanced Features
- **Position-specific rankings**: `--position QB|RB|WR|TE`
- **Custom top N players**: `--top 20`
- **Exclude injured players**: `--exclude-injured`
- **Sort by different metrics**: `--sort-by vorp|score|buzz|consistency`

## 📊 Understanding the Output

### VORP Analysis
The system uses Value Over Replacement Player (VORP) analysis to determine player value:
- **Positive VORP**: Player provides value above replacement level
- **Negative VORP**: Player is below replacement level
- **Higher VORP**: Better value for your draft position

### Ranking Tiers
- **Tier 1 (🥇)**: Elite players, draft early
- **Tier 2 (🥈)**: High-quality starters
- **Tier 3 (🥉)**: Solid contributors
- **Tier 4+**: Depth and bench options

## 🎯 Best Practices

1. **Run the full pipeline** before your draft to get the latest data
2. **Use VORP rankings** for optimal draft strategy
3. **Consider position scarcity** when making decisions
4. **Review news analysis** for injury updates and trends
5. **Use AI recommendations** as a guide, not gospel

## 🆘 Troubleshooting

Common issues and solutions are documented in the [CLI Guide](cli-guide.md#troubleshooting).

## 📞 Support

For additional help or questions, please refer to the component documentation or create an issue in the repository. 
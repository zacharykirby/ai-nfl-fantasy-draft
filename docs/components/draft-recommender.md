# NFL Fantasy Draft Recommender

## Overview

The `draft_recommender.py` script uses OpenRouter models to analyze top VORP-ranked players and provide strategic draft pick recommendations. It combines the ranking data with AI analysis to suggest optimal pick ordering based on position scarcity, team needs, and strategic considerations.

## Features

- **VORP-based Analysis**: Uses Value Over Replacement Player scores to identify the most valuable picks
- **Position Scarcity Analysis**: Considers which positions have limited elite options
- **Strategic Recommendations**: Provides detailed reasoning for each pick
- **Multi-round Planning**: Analyzes how early picks affect later round strategy
- **Risk/Reward Assessment**: Balances safe picks with high-ceiling players
- **Response Filtering**: Automatically removes internal thinking sections from reasoning models

## Prerequisites

1. **OpenRouter API Key**: Set `OPENROUTER_API_KEY` in your environment or `.env`
2. **Ranking Data**: Run the ranker first so `outputs/player_rankings.json` exists
3. **Python Dependencies**: Same as other scripts (pandas, requests, etc.)

## Usage

### Basic Usage

```bash
# Generate draft recommendations using default settings
python scripts/draft_recommender.py

# Analyze top 30 players instead of 50
python scripts/draft_recommender.py --top-n 30

# Verify OpenRouter connectivity from the main CLI
python scripts/cli.py --openrouter-smoke-test
```

### Advanced Options

```bash
# Use a different OpenRouter model
python scripts/draft_recommender.py --model deepseek/deepseek-v4-flash

# Or set environment variables
export OPENROUTER_API_KEY=your-api-key
export OPENROUTER_MODEL=deepseek/deepseek-v4-flash

# Save recommendations to file
python scripts/draft_recommender.py --save

# Specify custom output filename
python scripts/draft_recommender.py --save --output-file my_draft_plan.txt
```

### Command Line Arguments

- `--top-n`: Number of top VORP players to analyze (default: 50)
- `--pick-position`: Your snake draft position (default: 1)
- `--league-size`: Number of teams in the league (default: 8)
- `--model`: OpenRouter model slug (default: `OPENROUTER_MODEL` or `openai/gpt-4o-mini`)
- `--allow-stale-rankings`: Allow stale rankings for inspection only
- `--save`: Save recommendations to file
- `--output-file`: Custom output filename (auto-generated if not specified)

## Output Format

The script provides:

1. **Player Summary**: Table showing top VORP players with their scores and rankings
2. **Position Distribution**: Count of players by position in the analysis
3. **Tier Distribution**: Count of players by tier level
4. **Draft Recommendations**: AI-generated strategic advice including:
   - Round 1-3 pick recommendations with detailed reasoning
   - Position scarcity considerations
   - Risk/reward assessments
   - Best available players for rounds 4-6
   - Overall draft strategy insights

## Example Output

```
🏈 TOP PLAYERS BY VORP - DRAFT ANALYSIS
================================================================================
Rank Player               Pos Team VORP   Score Tier Pos Rank
--------------------------------------------------------------------------------
1    Christian McCaffrey  RB  SF   25.3   95.2  1    1
2    Tyreek Hill         WR  MIA  23.1   92.8  1    1
3    Travis Kelce        TE  KC   20.5   89.4  1    1
...

🎯 DRAFT RECOMMENDATIONS
================================================================================

## ROUND 1-3 DRAFT RECOMMENDATIONS

### Round 1
**Pick 1:** Christian McCaffrey - RB - SF
- VORP: 25.3
- Reasoning: Highest VORP score, proven elite RB1 with consistent production
- Position scarcity: HIGH - Elite RBs are scarce, secure top option early

**Pick 2:** Tyreek Hill - WR - MIA
- VORP: 23.1
- Reasoning: Elite WR1 with high ceiling, excellent QB situation
- Position scarcity: MEDIUM - Good WR depth available later

### Round 2
[Continue format for picks 3-4]

### Round 3
[Continue format for picks 5-6]

## BEST AVAILABLE FOR ROUNDS 4-6
[List of next 15 best picks with brief reasoning]

## DRAFT STRATEGY INSIGHTS
[Overall strategy recommendations]
```

## Integration with Full Pipeline

This script is designed to work with the complete NFL Fantasy Draft Forecast system:

1. **Data Ingestion**: `data_ingest.py` collects player statistics
2. **News Analysis**: `news_analyzer.py` processes recent news and sentiment
3. **Player Ranking**: `ranker.py` generates VORP-based rankings
4. **Draft Recommendations**: `draft_recommender.py` provides strategic advice

## Tips for Best Results

1. **Use Recent Rankings**: Run the ranker script first to ensure you have the latest data
2. **Choose Appropriate Model**: Larger models (8B+) provide more detailed analysis
3. **Consider League Settings**: Adjust draft rounds based on your league size
4. **Review Position Scarcity**: Pay attention to which positions have limited elite options
5. **Balance Risk/Reward**: Consider consistency vs ceiling potential for your risk tolerance

## Troubleshooting

- **OpenRouter Connection Issues**: Run `python scripts/cli.py --openrouter-smoke-test`
- **Model Not Found**: Verify the OpenRouter model slug in `OPENROUTER_MODEL` or `--model`
- **No Ranking Data**: Run the ranker script first to generate required data files
- **Timeout Errors**: Increase timeout or use a faster model for quicker responses
- **Response Formatting**: The script automatically filters out `<think>` sections from reasoning models

## File Outputs

When using `--save`, the script creates:
- `outputs/draft_recommendations_YYYYMMDD_HHMMSS.txt`: Timestamped recommendation file
- Or custom filename if specified with `--output-file` 

#!/usr/bin/env python3
"""
News Analyzer Module for NFL Fantasy Draft Assistant

This module uses OpenRouter models to analyze fantasy football news headlines and extract
relevant features that impact player fantasy value.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import time
import pandas as pd

from llm_client import OpenRouterClient, parse_json_object

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# OpenRouter configuration
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')

def load_nfl_roster() -> set:
    """Load current NFL roster to validate player names"""
    try:
        # Try to load from enhanced stats first
        roster_file = "data/enhanced_player_stats.csv"
        if os.path.exists(roster_file):
            df = pd.read_csv(roster_file)
            roster = set(df['player'].str.lower().tolist())
            logger.info(f"Loaded {len(roster)} players from enhanced roster")
            return roster
        
        # Fallback to base stats
        roster_file = "data/nfl_player_data.csv"
        if os.path.exists(roster_file):
            df = pd.read_csv(roster_file)
            player_col = 'player' if 'player' in df.columns else 'player_name'
            roster = set(df[player_col].dropna().str.lower().tolist())
            logger.info(f"Loaded {len(roster)} players from base roster")
            return roster
        
        # If no roster file exists, return empty set (will allow all names)
        logger.warning("No roster file found, skipping player validation")
        return set()
        
    except Exception as e:
        logger.error(f"Error loading NFL roster: {e}")
        return set()

def validate_player_name(player_name: str, nfl_roster: set) -> bool:
    """Validate if a player name exists in the NFL roster"""
    if not nfl_roster:  # If no roster loaded, allow all names
        return True
    
    # Check exact match first
    if player_name.lower() in nfl_roster:
        return True
    
    # Check for partial matches (handle nicknames, etc.)
    for roster_name in nfl_roster:
        if player_name.lower() in roster_name or roster_name in player_name.lower():
            return True
    
    return False

def setup_llm_client():
    """Setup OpenRouter client."""
    client = OpenRouterClient(model=OPENROUTER_MODEL)
    if not client.api_key:
        logger.error("OPENROUTER_API_KEY is not set")
        return None
    logger.info(f"Configured OpenRouter model {client.model}")
    return client

def create_analysis_prompt(headline: str, summary: str = "") -> str:
    """
    Create the analysis prompt for OpenRouter.
    
    Args:
        headline: The news headline
        summary: Optional summary/description
        
    Returns:
        Formatted prompt string
    """
    content = headline
    if summary:
        content += f"\n\nSummary: {summary}"
    
    prompt = f"""You are a fantasy football assistant. Given a football news headline or summary, analyze it and return a JSON object with key features that may impact fantasy football player value.

Here is the headline:
"{content}"

Return a JSON object with the following keys:
- "player": The player's name (or "unknown" if no specific player mentioned)
- "injury_flag": true if the player is currently or recently injured
- "injury_type": type of injury if known (e.g., "hamstring", "ACL", "concussion"). Use "unknown" if not specified.
- "role_change": true if the player is gaining or losing role or depth chart position
- "expected_usage": One of "starter", "rotational", "backup", or "unclear"
- "sentiment_score": From -1.0 (bad) to +1.0 (very positive)
- "buzz_score": From 0.0 to 1.0 (indicates hype or interest in player)
- "topics": List of topics mentioned (e.g., ["injury", "practice", "performance"])

Only return the JSON. No explanation."""
    
    return prompt

def analyze_headline(client: OpenRouterClient, headline: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Analyze a single headline using OpenRouter.
    
    Args:
        client: OpenRouter client
        headline: Headline dictionary with title, summary, etc.
        
    Returns:
        Analysis result dictionary or None if failed
    """
    try:
        prompt = create_analysis_prompt(headline['title'], headline.get('summary', ''))
        
        content = client.chat(
            messages=[
                {'role': 'system', 'content': 'Return only valid JSON. No prose.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        if content.startswith("Error:"):
            logger.error(content)
            return None
        
        # Try to parse JSON from the response
        try:
            analysis = parse_json_object(content)
            
            # Add metadata
            analysis['original_headline'] = headline['title']
            analysis['source'] = headline['source']
            analysis['published'] = headline['published']
            analysis['analyzed_at'] = datetime.now().isoformat()
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from OpenRouter response: {e}")
            logger.warning(f"Raw response: {content}")
            return None
            
    except Exception as e:
        logger.error(f"Error analyzing headline '{headline['title'][:50]}...': {str(e)}")
        return None

def process_single_player(player_name: str, analysis: Dict[str, Any], player_features: Dict[str, Dict[str, Any]], nfl_roster: set) -> None:
    """Process a single player's analysis and add to player_features."""
    # Validate player name against NFL roster
    if not validate_player_name(player_name, nfl_roster):
        logger.warning(f"Skipping non-NFL player: {player_name}")
        return
    
    if player_name not in player_features:
        player_features[player_name] = {
            'player': player_name,
            'headlines': [],
            'sentiment_scores': [],
            'buzz_scores': [],
            'injury_flags': [],
            'role_changes': [],
            'topics': set(),
            'latest_analysis': None
        }
    
    # Add headline
    player_features[player_name]['headlines'].append({
        'title': analysis['original_headline'],
        'source': analysis['source'],
        'published': analysis['published']
    })
    
    # Aggregate scores
    if 'sentiment_score' in analysis and analysis['sentiment_score'] is not None:
        player_features[player_name]['sentiment_scores'].append(analysis['sentiment_score'])
    
    if 'buzz_score' in analysis and analysis['buzz_score'] is not None:
        player_features[player_name]['buzz_scores'].append(analysis['buzz_score'])
    
    # Aggregate flags
    if analysis.get('injury_flag'):
        player_features[player_name]['injury_flags'].append(True)
    
    if analysis.get('role_change'):
        player_features[player_name]['role_changes'].append(True)
    
    # Aggregate topics
    if 'topics' in analysis and analysis['topics']:
        player_features[player_name]['topics'].update(analysis['topics'])
    
    # Keep track of latest analysis
    if not player_features[player_name]['latest_analysis'] or \
       analysis['published'] > player_features[player_name]['latest_analysis']['published']:
        player_features[player_name]['latest_analysis'] = analysis

def aggregate_player_features(analyses: List[Dict[str, Any]], nfl_roster: set) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate features by player name.
    
    Args:
        analyses: List of headline analyses
        nfl_roster: Set of valid NFL player names
        
    Returns:
        Dictionary of player features aggregated from all headlines
    """
    player_features = {}
    
    for analysis in analyses:
        if not analysis or 'player' not in analysis:
            continue
            
        player_name = analysis['player']
        
        # Handle case where player is a list (multiple players in one headline)
        if isinstance(player_name, list):
            # Process each player in the list
            for player in player_name:
                if isinstance(player, str) and player.lower() not in ['unknown', 'none', '']:
                    process_single_player(player, analysis, player_features, nfl_roster)
        elif isinstance(player_name, str) and player_name.lower() not in ['unknown', 'none', '']:
            process_single_player(player_name, analysis, player_features, nfl_roster)
    
    # Calculate aggregated metrics
    for player, features in player_features.items():
        # Average sentiment score
        if features['sentiment_scores']:
            features['avg_sentiment'] = sum(features['sentiment_scores']) / len(features['sentiment_scores'])
        else:
            features['avg_sentiment'] = 0.0
        
        # Average buzz score
        if features['buzz_scores']:
            features['avg_buzz'] = sum(features['buzz_scores']) / len(features['buzz_scores'])
        else:
            features['avg_buzz'] = 0.0
        
        # Overall injury flag (if any headline indicates injury)
        features['has_injury'] = len(features['injury_flags']) > 0
        
        # Overall role change flag
        features['has_role_change'] = len(features['role_changes']) > 0
        
        # Convert topics set to list
        features['all_topics'] = list(features['topics'])
        
        # Headline count
        features['headline_count'] = len(features['headlines'])
        
        # Remove raw lists to clean up output
        del features['sentiment_scores']
        del features['buzz_scores']
        del features['injury_flags']
        del features['role_changes']
        del features['topics']
    
    return player_features

def analyze_headlines(input_file: str = 'news/final_quality_headlines.json', 
                     output_file: str = 'news/player_features.json') -> None:
    """
    Analyze all headlines and save player features.
    
    Args:
        input_file: Path to raw headlines JSON file
        output_file: Path to save player features JSON file
    """
    logger.info("Starting headline analysis...")
    
    # Setup OpenRouter client
    client = setup_llm_client()
    if not client:
        logger.error("Cannot proceed without OpenRouter configuration")
        return
    
    # Load headlines
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        headlines = data.get('headlines', [])
        logger.info(f"Loaded {len(headlines)} headlines for analysis")
    except Exception as e:
        logger.error(f"Failed to load headlines from {input_file}: {str(e)}")
        return
    
    # Analyze each headline
    analyses = []
    for i, headline in enumerate(headlines):
        logger.info(f"Analyzing headline {i+1}/{len(headlines)}: {headline['title'][:50]}...")
        
        analysis = analyze_headline(client, headline)
        if analysis:
            analyses.append(analysis)
        
        # Small delay to avoid hammering the API.
        time.sleep(0.1)
    
    logger.info(f"Successfully analyzed {len(analyses)} headlines")
    
    # Aggregate by player
    nfl_roster = load_nfl_roster()
    player_features = aggregate_player_features(analyses, nfl_roster)
    
    # Save results
    output_data = {
        'metadata': {
            'analyzed_at': datetime.now().isoformat(),
            'total_headlines_analyzed': len(analyses),
            'players_found': len(player_features),
            'llm_provider': 'openrouter',
            'openrouter_model': client.model
        },
        'player_features': player_features
    }
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved player features for {len(player_features)} players to {output_file}")
    
    # Print summary
    if player_features:
        logger.info("Top players by buzz score:")
        sorted_players = sorted(player_features.items(), 
                              key=lambda x: x[1]['avg_buzz'], reverse=True)[:5]
        for player, features in sorted_players:
            logger.info(f"  {player}: {features['avg_buzz']:.2f} buzz, {features['headline_count']} headlines")

def main():
    """Main function to analyze headlines."""
    logger.info("Starting news analysis pipeline...")
    
    # Check if input file exists
    if not os.path.exists('news/final_quality_headlines.json'):
        logger.error("No headlines file found. Run news_fetcher.py first.")
        return
    
    analyze_headlines()
    logger.info("News analysis completed!")

if __name__ == "__main__":
    main() 

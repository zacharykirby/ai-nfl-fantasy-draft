#!/usr/bin/env python3
"""
News Analyzer Module for NFL Fantasy Draft Assistant

This module uses Ollama to analyze fantasy football news headlines and extract
relevant features that impact player fantasy value.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
import ollama
from datetime import datetime
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:14b')  # Default model, can be overridden

def setup_ollama_client():
    """Setup Ollama client with custom host if needed."""
    try:
        # Test connection to Ollama
        client = ollama.Client(host=OLLAMA_HOST)
        # Test with a simple request
        response = client.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': 'Hello'}])
        logger.info(f"Successfully connected to Ollama at {OLLAMA_HOST} using model {OLLAMA_MODEL}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Ollama at {OLLAMA_HOST}: {str(e)}")
        logger.info("Make sure Ollama is running and accessible. You can set OLLAMA_HOST environment variable if needed.")
        return None

def create_analysis_prompt(headline: str, summary: str = "") -> str:
    """
    Create the analysis prompt for Ollama.
    
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

def analyze_headline(client: ollama.Client, headline: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Analyze a single headline using Ollama.
    
    Args:
        client: Ollama client
        headline: Headline dictionary with title, summary, etc.
        
    Returns:
        Analysis result dictionary or None if failed
    """
    try:
        prompt = create_analysis_prompt(headline['title'], headline.get('summary', ''))
        
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1}  # Low temperature for consistent JSON output
        )
        
        # Extract the response content
        content = response['message']['content'].strip()
        
        # Try to parse JSON from the response
        try:
            # Remove <think> tags and content
            if '<think>' in content:
                start_idx = content.find('</think>')
                if start_idx != -1:
                    content = content[start_idx + 8:]  # Skip past </think>
            
            # Sometimes the model wraps JSON in code blocks, so we need to extract it
            if '```json' in content:
                # Find the start of the JSON content
                start_idx = content.find('```json') + 7
                content = content[start_idx:]
            elif content.startswith('```'):
                content = content[3:]
            
            # Remove closing backticks if present
            if content.endswith('```'):
                content = content[:-3]
            
            # Clean up any remaining whitespace and newlines
            content = content.strip()
            
            # Debug: log the cleaned content
            logger.debug(f"Cleaned content: '{content}'")
            logger.debug(f"Content length: {len(content)}")
            
            analysis = json.loads(content)
            
            # Add metadata
            analysis['original_headline'] = headline['title']
            analysis['source'] = headline['source']
            analysis['published'] = headline['published']
            analysis['analyzed_at'] = datetime.now().isoformat()
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from Ollama response: {e}")
            logger.warning(f"Raw response: {content}")
            return None
            
    except Exception as e:
        logger.error(f"Error analyzing headline '{headline['title'][:50]}...': {str(e)}")
        return None

def process_single_player(player_name: str, analysis: Dict[str, Any], player_features: Dict[str, Dict[str, Any]]) -> None:
    """Process a single player's analysis and add to player_features."""
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

def aggregate_player_features(analyses: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate features by player name.
    
    Args:
        analyses: List of headline analyses
        
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
                    process_single_player(player, analysis, player_features)
        elif isinstance(player_name, str) and player_name.lower() not in ['unknown', 'none', '']:
            process_single_player(player_name, analysis, player_features)
    
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

def analyze_headlines(input_file: str = 'news/raw_headlines.json', 
                     output_file: str = 'news/player_features.json') -> None:
    """
    Analyze all headlines and save player features.
    
    Args:
        input_file: Path to raw headlines JSON file
        output_file: Path to save player features JSON file
    """
    logger.info("Starting headline analysis...")
    
    # Setup Ollama client
    client = setup_ollama_client()
    if not client:
        logger.error("Cannot proceed without Ollama connection")
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
        
        # Small delay to be nice to the Ollama server
        time.sleep(0.1)
    
    logger.info(f"Successfully analyzed {len(analyses)} headlines")
    
    # Aggregate by player
    player_features = aggregate_player_features(analyses)
    
    # Save results
    output_data = {
        'metadata': {
            'analyzed_at': datetime.now().isoformat(),
            'total_headlines_analyzed': len(analyses),
            'players_found': len(player_features),
            'ollama_model': OLLAMA_MODEL,
            'ollama_host': OLLAMA_HOST
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
    if not os.path.exists('news/raw_headlines.json'):
        logger.error("No headlines file found. Run news_fetcher.py first.")
        return
    
    analyze_headlines()
    logger.info("News analysis completed!")

if __name__ == "__main__":
    main() 
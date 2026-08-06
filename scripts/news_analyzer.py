#!/usr/bin/env python3
"""
News Analyzer Module for NFL Fantasy Draft Assistant

This module uses OpenRouter models to analyze fantasy football news headlines and extract
relevant features that impact player fantasy value.
"""

import json
import logging
import os
import re
from pathlib import Path
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

EVENT_TYPES = {
    "none", "injury", "recovery", "suspension", "role_change", "trade", "release"
}
INJURY_STATUSES = {"none", "new", "worsening", "recovering", "cleared", "unknown"}
ROLE_DIRECTIONS = {"none", "gained", "lost", "competition", "unknown"}
EVENT_DIRECTIONS = {"positive", "negative", "neutral"}
ACTIONABLE_EVENT_TYPES = {"injury", "recovery", "suspension", "role_change", "release"}


def normalize_player_name(value: str) -> str:
    """Normalize common suffix/punctuation variants without fuzzy player guessing."""
    words = re.sub(r"[^a-z0-9 ]", " ", str(value).casefold()).split()
    while words and words[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        words.pop()
    return " ".join(words)


def _bounded_float(value: Any, low: float, high: float, default: float = 0.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def _enum(value: Any, allowed: set, default: str) -> str:
    normalized = str(value or "").casefold().strip().replace(" ", "_")
    return normalized if normalized in allowed else default


def normalize_event_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    """Validate model classifications and derive a conservative actionable flag."""
    result = dict(item)
    result["event_type"] = _enum(result.get("event_type"), EVENT_TYPES, "none")
    result["event_direction"] = _enum(
        result.get("event_direction"), EVENT_DIRECTIONS, "neutral"
    )
    result["injury_status"] = _enum(
        result.get("injury_status"), INJURY_STATUSES, "unknown"
    )
    result["role_direction"] = _enum(
        result.get("role_direction"), ROLE_DIRECTIONS, "unknown"
    )
    result["confidence"] = _bounded_float(result.get("confidence"), 0.0, 1.0)
    result["sentiment_score"] = _bounded_float(
        result.get("sentiment_score"), -1.0, 1.0
    )
    result["buzz_score"] = _bounded_float(result.get("buzz_score"), 0.0, 1.0)
    try:
        games = int(result.get("expected_games_missed"))
        result["expected_games_missed"] = max(0, min(18, games))
    except (TypeError, ValueError):
        result["expected_games_missed"] = None

    topics = result.get("topics")
    result["topics"] = [str(topic) for topic in topics] if isinstance(topics, list) else []

    concrete = False
    if result["event_type"] == "injury":
        concrete = result["injury_status"] in {"new", "worsening"}
    elif result["event_type"] == "recovery":
        concrete = result["injury_status"] in {"recovering", "cleared"}
    elif result["event_type"] == "role_change":
        concrete = result["role_direction"] in {"gained", "lost"}
    elif result["event_type"] in {"suspension", "release"}:
        concrete = result["event_direction"] == "negative"

    # The model may decline to call an event actionable, but cannot make an
    # ambiguous event actionable merely by setting a boolean.
    result["actionable"] = bool(result.get("actionable")) and concrete
    return result

def load_nfl_roster() -> set:
    """Load current NFL roster to validate player names"""
    try:
        roster = set()
        projection_files = sorted(Path("data").glob("players_*_positions_bye.csv"), reverse=True)
        if projection_files:
            projections = pd.read_csv(projection_files[0])
            roster.update(projections["name"].dropna().astype(str).str.lower())

        # Try to load from enhanced stats first
        roster_file = "data/enhanced_player_stats.csv"
        if os.path.exists(roster_file):
            df = pd.read_csv(roster_file)
            roster.update(df['player'].dropna().astype(str).str.lower())
            logger.info(f"Loaded {len(roster)} players from enhanced roster")
            return roster
        
        # Fallback to base stats
        roster_file = "data/nfl_player_data.csv"
        if os.path.exists(roster_file):
            df = pd.read_csv(roster_file)
            player_col = 'player' if 'player' in df.columns else 'player_name'
            roster.update(df[player_col].dropna().astype(str).str.lower())
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

def create_analysis_prompt(
    headline: str,
    summary: str = "",
    candidate_players: Optional[List[str]] = None,
) -> str:
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
    
    candidates = ", ".join(candidate_players or []) or "none supplied"
    prompt = f"""You are a fantasy football assistant. Given a football news headline or summary, analyze it and return a JSON object with key features that may impact fantasy football player value.

Here is the headline:
"{content}"

Current fantasy players identified by deterministic matching: {candidates}

Return a JSON object with an "analyses" array containing one object per materially discussed identified player. Each object must have:
- "player": Exactly one name from the identified-player list above. Do not invent a different player.
- "event_type": One of "none", "injury", "recovery", "suspension", "role_change", "trade", or "release". Contracts, rankings, awards, opinions, and generic hype are "none".
- "event_direction": One of "positive", "negative", or "neutral"
- "actionable": true only when the report confirms a change to availability or depth-chart role; speculation and competitions are false
- "confidence": From 0.0 to 1.0 based only on how explicit the supplied text is
- "injury_flag": true only if the player is currently limited or unavailable, not merely because an old injury is mentioned
- "injury_type": type of injury if known (e.g., "hamstring", "ACL", "concussion"). Use "unknown" if not specified.
- "injury_status": One of "none", "new", "worsening", "recovering", "cleared", or "unknown"
- "expected_games_missed": Integer 0-18 only when explicitly stated or null
- "role_change": true only for a confirmed gain or loss, not a competition
- "role_direction": One of "none", "gained", "lost", "competition", or "unknown"
- "expected_usage": One of "starter", "rotational", "backup", or "unclear"
- "sentiment_score": From -1.0 (bad) to +1.0 (very positive)
- "buzz_score": From 0.0 to 1.0 (indicates hype or interest in player)
- "topics": List of topics mentioned (e.g., ["injury", "practice", "performance"])

Do not infer facts absent from the headline/summary. A positive recovery update is "recovery", not a new injury. Only return the JSON. No explanation."""
    
    return prompt


def normalize_analysis_payload(
    payload: Any,
    candidate_players: List[str],
) -> List[Dict[str, Any]]:
    """Normalize model JSON and make deterministic name matching authoritative."""
    if isinstance(payload, dict) and isinstance(payload.get("analyses"), list):
        model_items = [dict(item) for item in payload["analyses"] if isinstance(item, dict)]
    elif isinstance(payload, dict):
        model_items = [dict(payload)]
    elif isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        model_items = [dict(item) for item in payload]
    else:
        raise ValueError("OpenRouter analysis must be a JSON object or list of objects")

    if not candidate_players:
        analysis = model_items[0]
        analysis["player"] = "unknown"
        return [analysis]

    by_name = {
        normalize_player_name(str(item.get("player") or "")): item
        for item in model_items
        if isinstance(item.get("player"), str)
    }
    normalized = []
    for index, candidate in enumerate(candidate_players):
        source = by_name.get(normalize_player_name(candidate))
        if source is None and len(candidate_players) == 1 and len(model_items) == 1:
            source = model_items[0]
        # Never positionally copy one player's injury/role event to a different
        # candidate in a multi-player headline.
        analysis = dict(source) if source is not None else {
            "event_type": "none",
            "event_direction": "neutral",
            "actionable": False,
            "confidence": 0.0,
            "injury_flag": False,
            "injury_status": "unknown",
            "role_change": False,
            "role_direction": "unknown",
            "sentiment_score": 0.0,
            "buzz_score": 0.0,
            "topics": [],
        }
        analysis["player"] = candidate
        normalized.append(normalize_event_fields(analysis))
    return normalized

def analyze_headline(client: OpenRouterClient, headline: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Analyze a single headline using OpenRouter.
    
    Args:
        client: OpenRouter client
        headline: Headline dictionary with title, summary, etc.
        
    Returns:
        Analysis result dictionary or None if failed
    """
    try:
        prompt = create_analysis_prompt(
            headline['title'],
            headline.get('summary', ''),
            headline.get('player_names') or [],
        )
        
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
            candidates = headline.get('player_names') or []
            analyses = normalize_analysis_payload(parse_json_object(content), candidates)

            # Add metadata to each player-specific result.
            for analysis in analyses:
                analysis['original_headline'] = headline['title']
                analysis['source'] = headline['source']
                analysis['published'] = headline['published']
                analysis['link'] = headline.get('link', '')
                analysis['source_quality'] = _bounded_float(
                    headline.get('source_quality', 0.7), 0.0, 1.0, 0.7
                )
                analysis['analyzed_at'] = datetime.now().isoformat()

            return analyses
            
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
            'events': [],
            'topics': set(),
            'latest_analysis': None
        }
    
    # Add headline
    player_features[player_name]['headlines'].append({
        'title': analysis['original_headline'],
        'source': analysis['source'],
        'published': analysis['published'],
        'link': analysis.get('link', ''),
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

    event = {
        key: analysis.get(key)
        for key in (
            "event_type", "event_direction", "actionable", "confidence",
            "injury_flag", "injury_type", "injury_status", "expected_games_missed",
            "role_change", "role_direction", "expected_usage", "published", "source",
            "source_quality", "link", "original_headline",
        )
    }
    player_features[player_name]['events'].append(event)
    
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
        
        def event_date(event: Dict[str, Any]) -> datetime:
            try:
                return datetime.fromisoformat(str(event.get("published") or "").replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return datetime.min

        # Collapse repeated coverage of the same player event and make the newest
        # status authoritative. Availability combines injury and recovery so a
        # return-to-practice report supersedes an older injury report.
        latest_by_category: Dict[str, Dict[str, Any]] = {}
        for event in sorted(features['events'], key=event_date):
            event_type = str(event.get("event_type") or "none")
            if event_type in {"injury", "recovery"}:
                category = "availability"
            elif event_type in {"role_change", "suspension", "release"}:
                category = event_type
            else:
                continue
            current = latest_by_category.get(category)
            if current is None or event_date(event) >= event_date(current):
                latest_by_category[category] = event

        actionable_events = [
            event for event in latest_by_category.values()
            if event.get("actionable") and float(event.get("confidence") or 0) >= 0.65
        ]
        availability = latest_by_category.get("availability", {})
        role = latest_by_category.get("role_change", {})
        features['has_injury'] = (
            availability.get("event_type") == "injury"
            and availability.get("injury_status") in {"new", "worsening"}
        )
        features['has_role_change'] = role.get("role_direction") in {"gained", "lost"}
        features['actionable_events'] = sorted(actionable_events, key=event_date, reverse=True)
        features['latest_actionable_event'] = (
            features['actionable_events'][0] if features['actionable_events'] else None
        )
        
        # Convert topics set to list
        features['all_topics'] = list(features['topics'])
        
        # Headline count
        features['headline_count'] = len(features['headlines'])
        
        # Remove raw lists to clean up output
        del features['sentiment_scores']
        del features['buzz_scores']
        del features['injury_flags']
        del features['role_changes']
        del features['events']
        del features['topics']
    
    return player_features

def analyze_headlines(
    input_file: str = 'news/final_quality_headlines.json',
    output_file: str = 'news/player_features.json',
    max_headlines: Optional[int] = 30,
) -> Optional[Dict[str, Any]]:
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
        source_headline_count = len(headlines)
        if max_headlines is not None:
            headlines = headlines[:max(0, int(max_headlines))]
        logger.info(f"Loaded {len(headlines)} headlines for analysis")
    except Exception as e:
        logger.error(f"Failed to load headlines from {input_file}: {str(e)}")
        return None
    
    # Analyze each headline
    analyses = []
    successful_headlines = 0
    for i, headline in enumerate(headlines):
        logger.info(f"Analyzing headline {i+1}/{len(headlines)}: {headline['title'][:50]}...")
        
        headline_analyses = analyze_headline(client, headline)
        if headline_analyses:
            analyses.extend(headline_analyses)
            successful_headlines += 1
        
        # Small delay to avoid hammering the API.
        time.sleep(0.1)
    
    logger.info(f"Successfully analyzed {successful_headlines} headlines")
    
    # Aggregate by player
    nfl_roster = load_nfl_roster()
    player_features = aggregate_player_features(analyses, nfl_roster)
    
    # Save results
    output_data = {
        'metadata': {
            'analyzed_at': datetime.now().isoformat(),
            'source_headline_count': source_headline_count,
            'total_headlines_analyzed': successful_headlines,
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
    return output_data

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

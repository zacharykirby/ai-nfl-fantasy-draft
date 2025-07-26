#!/usr/bin/env python3
"""
News Fetcher Module for NFL Fantasy Draft Assistant

This module fetches fantasy football news headlines from various RSS feeds
and stores them in a structured JSON format for later analysis.
"""

import feedparser
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import time
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RSS Feed URLs for fantasy football news
RSS_FEEDS = {
    'rotoworld': 'https://www.nbcsports.com/rss/fantasy/football',
    'rotowire': 'https://www.rotowire.com/rss/fantasy/football.xml',
    'draftsharks': 'https://www.draftsharks.com/feed',
    'fantasypros': 'https://www.fantasypros.com/feed/',
    'espn_fantasy': 'https://www.espn.com/espn/rss/fantasy/news'
}

def fetch_headlines(max_age_hours: int = 24) -> List[Dict[str, Any]]:
    """
    Fetch headlines from all configured RSS feeds.
    
    Args:
        max_age_hours: Only fetch headlines from the last N hours
        
    Returns:
        List of headline dictionaries
    """
    all_headlines = []
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            logger.info(f"Fetching headlines from {source_name}...")
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                logger.warning(f"Feed parsing error for {source_name}: {feed.bozo_exception}")
                continue
                
            for entry in feed.entries:
                # Parse publication date
                pub_time = time.mktime(entry.get('published_parsed', time.localtime()))
                
                # Skip old headlines
                if pub_time < cutoff_time:
                    continue
                    
                headline = {
                    'title': entry.get('title', ''),
                    'summary': entry.get('summary', ''),
                    'link': entry.get('link', ''),
                    'source': source_name,
                    'published': datetime.fromtimestamp(pub_time).isoformat(),
                    'raw_content': entry.get('content', [{}])[0].get('value', '') if entry.get('content') else ''
                }
                
                all_headlines.append(headline)
                
            logger.info(f"Fetched {len([h for h in all_headlines if h['source'] == source_name])} headlines from {source_name}")
            
        except Exception as e:
            logger.error(f"Error fetching from {source_name}: {str(e)}")
            continue
    
    logger.info(f"Total headlines fetched: {len(all_headlines)}")
    return all_headlines

def save_headlines(headlines: List[Dict[str, Any]], output_file: str = 'news/raw_headlines.json') -> None:
    """
    Save headlines to JSON file.
    
    Args:
        headlines: List of headline dictionaries
        output_file: Output file path
    """
    # Ensure news directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    output_data = {
        'metadata': {
            'fetched_at': datetime.now().isoformat(),
            'total_headlines': len(headlines),
            'sources': list(set(h['source'] for h in headlines))
        },
        'headlines': headlines
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(headlines)} headlines to {output_file}")

def main():
    """Main function to fetch and save headlines."""
    logger.info("Starting news headline fetch...")
    
    # Fetch headlines from the last 24 hours
    headlines = fetch_headlines(max_age_hours=24)
    
    if headlines:
        save_headlines(headlines)
        logger.info("News fetch completed successfully!")
    else:
        logger.warning("No headlines were fetched. Check RSS feed URLs and connectivity.")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
News Fetcher Module for NFL Fantasy Draft Assistant

This module fetches fantasy football news headlines from various RSS feeds
and stores them in a structured JSON format for later analysis.
"""

import feedparser
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time
import os
import re
import requests
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Updated RSS Feed URLs for fantasy football news (more specific to football)
RSS_FEEDS = {
    'fantasypros_football': 'https://www.fantasypros.com/nfl/feed/',
    'espn_fantasy_football': 'https://www.espn.com/espn/rss/fantasy/news',
    'rotoworld_football': 'https://www.nbcsports.com/rss/fantasy/football',
    'rotowire_football': 'https://www.rotowire.com/rss/fantasy/football.xml',
    'cbs_fantasy_football': 'https://www.cbssports.com/rss/fantasy/football',
    'yahoo_fantasy_football': 'https://sports.yahoo.com/fantasy/football/rss.xml',
    'bleacher_report_fantasy': 'https://bleacherreport.com/fantasy-football.rss',
    'numberfire_fantasy': 'https://www.numberfire.com/nfl/fantasy-football/rss',
    'fftoday_fantasy': 'https://www.fftoday.com/rss/fantasy_football.xml',
    'footballguys_fantasy': 'https://www.footballguys.com/rss/fantasy-football.xml',
    # Alternative feeds that might work better
    'fantasypros_articles': 'https://www.fantasypros.com/feed/',
    'espn_nfl': 'https://www.espn.com/espn/rss/nfl/news',
    'nfl_news': 'https://www.nfl.com/rss/rsslanding?searchString=news',
    'profootballtalk': 'https://profootballtalk.nbcsports.com/feed/',
    'rotoworld_nfl': 'https://www.rotoworld.com/rss/nfl.xml',
    'sporting_news_fantasy': 'https://www.sportingnews.com/us/fantasy/rss.xml'
}

# Football-specific keywords to filter content
FOOTBALL_KEYWORDS = [
    'fantasy football', 'nfl', 'football', 'quarterback', 'qb', 'running back', 'rb',
    'wide receiver', 'wr', 'tight end', 'te', 'kicker', 'defense', 'def', 'draft',
    'adp', 'rankings', 'sleepers', 'busts', 'injury', 'trade', 'waiver wire',
    'christian mccaffrey', 'saquon barkley', 'justin jefferson', 'jamarr chase',
    'tyreek hill', 'austin ekeler', 'derrick henry', 'josh allen', 'patrick mahomes',
    'jalen hurts', 'lamar jackson', 'joe burrow', 'kyler murray', 'dak prescott'
]

# Baseball keywords to exclude
BASEBALL_KEYWORDS = [
    'mlb', 'baseball', 'pitcher', 'hitter', 'home run', 'rbi', 'era', 'whip',
    'fantasy baseball', 'baseball dfs', 'mlb dfs', 'baseball draft'
]

def is_football_related(title: str, summary: str) -> bool:
    """
    Check if a headline is football-related based on keywords.
    
    Args:
        title: Article title
        summary: Article summary
        
    Returns:
        True if football-related, False otherwise
    """
    content = (title + ' ' + summary).lower()
    
    # Check for baseball keywords first (exclude these)
    for keyword in BASEBALL_KEYWORDS:
        if keyword in content:
            return False
    
    # Check for football keywords
    for keyword in FOOTBALL_KEYWORDS:
        if keyword in content:
            return True
    
    return False

def clean_text(text: str) -> str:
    """
    Clean HTML and special characters from text.
    
    Args:
        text: Raw text with HTML
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove HTML entities
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    text = re.sub(r'&#\d+;', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def fetch_headlines(max_age_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Fetch headlines from all configured RSS feeds.
    
    Args:
        max_age_hours: Only fetch headlines from the last N hours (default: 168 = 1 week)
        
    Returns:
        List of headline dictionaries
    """
    all_headlines = []
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            logger.info(f"Fetching headlines from {source_name}...")
            
            # Add headers to mimic a browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache'
            }
            
            # Try multiple approaches to fetch the feed
            feed = None
            
            # Method 1: Try with requests first
            try:
                response = requests.get(feed_url, headers=headers, timeout=15)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                if feed.entries:
                    logger.info(f"Successfully fetched {len(feed.entries)} entries from {source_name} via requests")
            except requests.RequestException as e:
                logger.debug(f"Requests failed for {source_name}: {e}")
            
            # Method 2: Try direct feedparser if requests failed
            if not feed or not feed.entries:
                try:
                    feed = feedparser.parse(feed_url)
                    if feed.entries:
                        logger.info(f"Successfully fetched {len(feed.entries)} entries from {source_name} via feedparser")
                except Exception as e:
                    logger.debug(f"Feedparser failed for {source_name}: {e}")
            
            # Skip if we couldn't get any entries
            if not feed or not feed.entries:
                logger.warning(f"No entries found for {source_name}")
                continue
            
            if feed.bozo:
                logger.warning(f"Feed parsing error for {source_name}: {feed.bozo_exception}")
                # Continue anyway, some feeds might still have usable entries
                
            football_headlines = 0
            total_headlines = 0
            
            for entry in feed.entries:
                total_headlines += 1
                
                # Parse publication date - handle different date formats
                pub_time = None
                if entry.get('published_parsed'):
                    pub_time = time.mktime(entry.published_parsed)
                elif entry.get('updated_parsed'):
                    pub_time = time.mktime(entry.updated_parsed)
                else:
                    # If no date, assume it's recent
                    pub_time = time.time()
                
                # Skip old headlines
                if pub_time < cutoff_time:
                    continue
                
                # Clean the title and summary
                title = clean_text(entry.get('title', ''))
                summary = clean_text(entry.get('summary', ''))
                
                # Check if it's football-related
                if not is_football_related(title, summary):
                    continue
                
                headline = {
                    'title': title,
                    'summary': summary,
                    'link': entry.get('link', ''),
                    'source': source_name,
                    'published': datetime.fromtimestamp(pub_time).isoformat(),
                    'raw_content': clean_text(entry.get('content', [{}])[0].get('value', '')) if entry.get('content') else ''
                }
                
                all_headlines.append(headline)
                football_headlines += 1
                
            logger.info(f"Fetched {football_headlines}/{total_headlines} football headlines from {source_name}")
            
        except Exception as e:
            logger.error(f"Error fetching from {source_name}: {str(e)}")
            continue
    
    # Sort by publication date (newest first)
    all_headlines.sort(key=lambda x: x['published'], reverse=True)
    
    logger.info(f"Total football headlines fetched: {len(all_headlines)}")
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
            'sources': list(set(h['source'] for h in headlines)),
            'date_range': f"Last {len(headlines)} football headlines from various sources"
        },
        'headlines': headlines
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(headlines)} football headlines to {output_file}")

def main():
    """Main function to fetch and save headlines."""
    logger.info("Starting fantasy football news headline fetch...")
    
    # Fetch headlines from the last 2 weeks (336 hours)
    headlines = fetch_headlines(max_age_hours=336)
    
    if headlines:
        save_headlines(headlines)
        logger.info("News fetch completed successfully!")
        
        # Print a summary of what was fetched
        print(f"\n=== FETCH SUMMARY ===")
        print(f"Total football headlines: {len(headlines)}")
        print(f"Sources: {', '.join(set(h['source'] for h in headlines))}")
        print(f"Date range: {headlines[-1]['published'][:10]} to {headlines[0]['published'][:10]}")
        print(f"\nSample headlines:")
        for i, headline in enumerate(headlines[:5]):
            print(f"{i+1}. {headline['title'][:80]}... ({headline['source']})")
    else:
        logger.warning("No football headlines were fetched. Check RSS feed URLs and connectivity.")

if __name__ == "__main__":
    main() 
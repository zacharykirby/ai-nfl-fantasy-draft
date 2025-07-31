#!/usr/bin/env python3
"""
Enhanced News Fetcher Module for NFL Fantasy Draft Assistant

This module fetches fantasy football news headlines from various RSS feeds
and stores them in a structured JSON format for later analysis.
Enhanced version with more sources, better error handling, and archive scraping.
Final quality-focused version with rule-based filtering for player names and relevance.
"""

import feedparser
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
import os
import re
import requests
from urllib.parse import urljoin, urlparse
import random
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Enhanced RSS Feed URLs - updated and expanded with working feeds
RSS_FEEDS = {
    # Working feeds from current version
    'espn_fantasy_football': 'https://www.espn.com/espn/rss/fantasy/news',
    'espn_nfl': 'https://www.espn.com/espn/rss/nfl/news',
    'fantasypros_articles': 'https://www.fantasypros.com/feed/',
    'profootballtalk': 'https://profootballtalk.nbcsports.com/feed/',
    'yahoo_nfl': 'https://sports.yahoo.com/nfl/rss.xml',
    'yahoo_fantasy': 'https://sports.yahoo.com/fantasy/rss.xml',
    'the_athletic_nfl': 'https://theathletic.com/rss/nfl/',
    
    # New working feeds discovered
    'espn_fantasy_rankings': 'https://www.espn.com/espn/rss/fantasy/rankings',
    'espn_nfl_rumors': 'https://www.espn.com/espn/rss/nfl/rumors',
    'yahoo_nfl_news': 'https://sports.yahoo.com/nfl/news/rss.xml',
    
    # Additional working feeds
    'espn_nfl_analysis': 'https://www.espn.com/espn/rss/nfl/analysis',
    'espn_fantasy_analysis': 'https://www.espn.com/espn/rss/fantasy/analysis',
}

# Additional archive/news sites to scrape (non-RSS)
ARCHIVE_SOURCES = {
    'cbs_archive': 'https://www.cbssports.com/nfl/news/',
    'yahoo_archive': 'https://sports.yahoo.com/nfl/news/',
    'nfl_com_archive': 'https://www.nfl.com/news/',
    'profootballtalk_archive': 'https://profootballtalk.nbcsports.com/category/rumor-mill/',
    
    # Additional archive sources
    'fantasypros_archive': 'https://www.fantasypros.com/nfl/news/',
    'yahoo_fantasy_archive': 'https://sports.yahoo.com/fantasy/football/news/',
    'the_athletic_archive': 'https://theathletic.com/nfl/',
    'yahoo_nfl_analysis_archive': 'https://sports.yahoo.com/nfl/analysis/',
    'profootballtalk_analysis_archive': 'https://profootballtalk.nbcsports.com/category/analysis/',
    'yahoo_fantasy_rankings_archive': 'https://sports.yahoo.com/fantasy/football/rankings/',
}

# Enhanced football-specific keywords
FOOTBALL_KEYWORDS = [
    # General football terms
    'fantasy football', 'nfl', 'football', 'nfl draft', 'training camp', 'preseason',
    'regular season', 'playoffs', 'super bowl', 'pro bowl',
    
    # Positions
    'quarterback', 'qb', 'running back', 'rb', 'wide receiver', 'wr', 'tight end', 'te',
    'kicker', 'defense', 'def', 'defensive', 'offensive', 'linebacker', 'cornerback',
    'safety', 'defensive end', 'defensive tackle', 'offensive line', 'guard', 'tackle',
    'center', 'fullback', 'fb', 'punter', 'long snapper',
    
    # Fantasy terms
    'adp', 'rankings', 'sleepers', 'busts', 'injury', 'trade', 'waiver wire',
    'fantasy points', 'ppr', 'standard', 'half ppr', 'dynasty', 'redraft',
    'mock draft', 'draft strategy', 'fantasy advice', 'start em sit em',
    
    # Common player names (top players)
    'christian mccaffrey', 'saquon barkley', 'justin jefferson', 'jamarr chase',
    'tyreek hill', 'austin ekeler', 'derrick henry', 'josh allen', 'patrick mahomes',
    'jalen hurts', 'lamar jackson', 'joe burrow', 'kyler murray', 'dak prescott',
    'tua tagovailoa', 'justin herbert', 'trevor lawrence', 'jordan love',
    'bijan robinson', 'jonathan taylor', 'nick chubb', 'alvin kamara',
    'stefon diggs', 'aj brown', 'cee dee lamb', 'amari cooper', 'mike evans',
    'travis kelce', 'mark andrews', 'george kittle', 'sam laporta',
    
    # Team names
    'chiefs', 'ravens', 'bills', 'bengals', 'dolphins', 'jets', 'patriots', 'steelers',
    'browns', 'broncos', 'raiders', 'chargers', 'texans', 'colts', 'jaguars', 'titans',
    'cowboys', 'eagles', 'giants', 'commanders', 'packers', 'lions', 'vikings', 'bears',
    'falcons', 'panthers', 'saints', 'buccaneers', 'rams', '49ers', 'seahawks', 'cardinals'
]

# Baseball keywords to exclude (expanded)
BASEBALL_KEYWORDS = [
    'mlb', 'baseball', 'pitcher', 'hitter', 'home run', 'rbi', 'era', 'whip',
    'fantasy baseball', 'baseball dfs', 'mlb dfs', 'baseball draft', 'spring training',
    'world series', 'all star game', 'baseball stats', 'batting average', 'reds',
    'duran', 'gold glove', 'silver slugger', 'cy young', 'mvp', 'roty', 'all-star',
    'baseball player', 'baseball team', 'baseball game', 'baseball season',
    'baseball league', 'baseball championship', 'baseball playoffs', 'baseball final',
    'baseball score', 'baseball result', 'baseball news', 'baseball update',
    'baseball injury', 'baseball trade', 'baseball signing', 'baseball contract',
    'baseball roster', 'baseball lineup', 'baseball rotation', 'baseball bullpen',
    'baseball catcher', 'baseball infield', 'baseball outfield', 'baseball manager',
    'baseball coach', 'baseball umpire', 'baseball stadium', 'baseball field',
    'baseball diamond', 'baseball mound', 'baseball plate', 'baseball base',
    'baseball inning', 'baseball out', 'baseball strike', 'baseball ball',
    'baseball bat', 'baseball glove', 'baseball helmet', 'baseball uniform'
]

# Basketball keywords to exclude (expanded)
BASKETBALL_KEYWORDS = [
    'nba', 'basketball', 'point guard', 'shooting guard', 'small forward', 'power forward',
    'center', 'fantasy basketball', 'basketball dfs', 'nba dfs', 'basketball draft',
    'playoffs', 'championship', 'all star', 'basketball stats', 'points per game',
    'bronny james', 'lebron james', 'stephen curry', 'kevin durant', 'giannis',
    'nikola jokic', 'joel embiid', 'luka doncic', 'jayson tatum', 'jimmy butler',
    'basketball player', 'basketball team', 'basketball game', 'basketball season',
    'basketball league', 'basketball championship', 'basketball playoffs', 'basketball final',
    'basketball score', 'basketball result', 'basketball news', 'basketball update',
    'basketball injury', 'basketball trade', 'basketball signing', 'basketball contract',
    'basketball roster', 'basketball lineup', 'basketball rotation', 'basketball bench',
    'basketball coach', 'basketball referee', 'basketball arena', 'basketball court',
    'basketball hoop', 'basketball rim', 'basketball net', 'basketball backboard',
    'basketball quarter', 'basketball period', 'basketball timeout', 'basketball foul',
    'basketball free throw', 'basketball three pointer', 'basketball dunk', 'basketball layup',
    'basketball rebound', 'basketball assist', 'basketball steal', 'basketball block',
    'basketball turnover', 'basketball possession', 'basketball defense', 'basketball offense'
]

def is_football_related(title: str, summary: str) -> bool:
    """
    Enhanced check if a headline is football-related based on keywords.
    
    Args:
        title: Article title
        summary: Article summary
        
    Returns:
        True if football-related, False otherwise
    """
    content = (title + ' ' + summary).lower()
    
    # Check for exclusion keywords first
    for keyword in BASEBALL_KEYWORDS + BASKETBALL_KEYWORDS:
        if keyword in content:
            return False
    
    # Check for football keywords
    for keyword in FOOTBALL_KEYWORDS:
        if keyword in content:
            return True
    
    # Additional checks for common football patterns
    if re.search(r'\b(nfl|football)\b', content):
        return True
    
    # Check for team abbreviations (3-letter codes)
    if re.search(r'\b[A-Z]{3}\b', title.upper()):
        return True
    
    return False

def has_player_name(title: str) -> bool:
    """
    Check if headline contains a player name (last name).
    
    Args:
        title: Article title
        
    Returns:
        True if contains player name, False otherwise
    """
    # Common NFL player last names (top players and common names)
    player_names = [
        'mccaffrey', 'barkley', 'jefferson', 'chase', 'hill', 'ekeler', 'henry',
        'allen', 'mahomes', 'hurts', 'jackson', 'burrow', 'murray', 'prescott',
        'tagovailoa', 'herbert', 'lawrence', 'love', 'robinson', 'taylor', 'chubb',
        'kamara', 'diggs', 'brown', 'lamb', 'cooper', 'evans', 'kelce', 'andrews',
        'kittle', 'laporta', 'adams', 'hopkins', 'thomas', 'jones', 'williams',
        'johnson', 'smith', 'davis', 'wilson', 'miller', 'moore', 'white', 'cook',
        'gordon', 'bell', 'gurley', 'elliot', 'zeke', 'saquon', 'cmc', 'tyreek',
        'aj', 'cee dee', 'stefon', 'travis', 'mark', 'george', 'sam', 'bijan',
        'justin', 'patrick', 'jalen', 'lamar', 'joe', 'kyler', 'dak', 'tua',
        'trevor', 'jordan', 'nick', 'alvin', 'mike', 'derrick', 'austin',
        'darrisaw', 'maye', 'emerson', 'schottenheimer', 'guyton', 'wright',
        'mendoza', 'skule', 'stefanski', 'watson', 'rodgers', 'brady', 'manning',
        'brees', 'rivers', 'roethlisberger', 'wilson', 'stafford', 'cousins',
        'carr', 'winston', 'mariota', 'trubisky', 'darnold', 'rosen', 'mayfield',
        'darnold', 'rosen', 'mayfield', 'darnold', 'rosen', 'mayfield'
    ]
    
    title_lower = title.lower()
    for name in player_names:
        if name in title_lower:
            return True
    
    # Check for patterns like "Player Name" or "Name, Player"
    if re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', title):
        return True
    
    return False

def extract_player_names(title: str) -> List[str]:
    """
    Extract known NFL player names from headline.
    
    Args:
        title: Article title
        
    Returns:
        List of player names found
    """
    known_players = [
        'christian mccaffrey', 'saquon barkley', 'justin jefferson', 'jamarr chase',
        'tyreek hill', 'austin ekeler', 'derrick henry', 'josh allen', 'patrick mahomes',
        'jalen hurts', 'lamar jackson', 'joe burrow', 'kyler murray', 'dak prescott',
        'tua tagovailoa', 'justin herbert', 'trevor lawrence', 'jordan love',
        'bijan robinson', 'jonathan taylor', 'nick chubb', 'alvin kamara',
        'stefon diggs', 'aj brown', 'cee dee lamb', 'amari cooper', 'mike evans',
        'travis kelce', 'mark andrews', 'george kittle', 'sam laporta',
        'darrisaw', 'maye', 'emerson', 'schottenheimer', 'guyton', 'wright',
        'mendoza', 'skule', 'stefanski', 'watson', 'rodgers', 'brady', 'manning',
        'brees', 'rivers', 'roethlisberger', 'wilson', 'stafford', 'cousins',
        'carr', 'winston', 'mariota', 'trubisky', 'darnold', 'rosen', 'mayfield'
    ]
    
    found_players = []
    title_lower = title.lower()
    
    for player in known_players:
        if player in title_lower:
            found_players.append(player)
    
    # Also look for "FirstName LastName" patterns
    name_patterns = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', title)
    for name in name_patterns:
        if name.lower() not in found_players:
            found_players.append(name)
    
    return found_players

def assess_headline_quality(title: str, summary: str) -> Dict[str, Any]:
    """
    Rule-based assessment of headline quality and relevance.
    
    Args:
        title: Article title
        summary: Article summary
        
    Returns:
        Dictionary with quality assessment
    """
    # Base score starts at 5
    score = 5
    
    # Check if football-related (+2 points)
    if is_football_related(title, summary):
        score += 2
    
    # Check if has player name (+3 points)
    if has_player_name(title):
        score += 3
    
    # Extract player names
    player_names = extract_player_names(title)
    
    # Bonus for multiple players (+1 point per additional player, max +2)
    if len(player_names) > 1:
        score += min(len(player_names) - 1, 2)
    
    # Bonus for specific keywords that indicate high relevance
    high_value_keywords = ['injury', 'trade', 'signing', 'contract', 'draft', 'fantasy', 'adp', 'rankings']
    for keyword in high_value_keywords:
        if keyword in title.lower():
            score += 1
            break
    
    # Penalty for generic terms
    generic_terms = ['news', 'update', 'report', 'latest', 'breaking']
    for term in generic_terms:
        if term in title.lower() and len(title.split()) < 8:
            score -= 1
            break
    
    # Ensure score is within 1-10 range
    score = max(1, min(10, score))
    
    # Determine if high quality (threshold of 7 or higher)
    is_high_quality = score >= 7
    
    return {
        "is_high_quality": is_high_quality,
        "has_player_name": has_player_name(title),
        "player_names": player_names,
        "relevance_score": score,
        "reason": f"Rule-based assessment: football={is_football_related(title, summary)}, player={has_player_name(title)}, score={score}"
    }

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

def get_random_user_agent() -> str:
    """Get a random user agent to avoid being blocked."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ]
    return random.choice(user_agents)

def fetch_rss_feed(feed_url: str, source_name: str) -> Optional[feedparser.FeedParserDict]:
    """
    Fetch RSS feed with enhanced error handling and retry logic.
    
    Args:
        feed_url: RSS feed URL
        source_name: Name of the source for logging
        
    Returns:
        Parsed feed or None if failed
    """
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }
    
    # Try multiple approaches to fetch the feed
    for attempt in range(3):
        try:
            # Method 1: Try with requests first
            response = requests.get(feed_url, headers=headers, timeout=20)
            response.raise_for_status()
            
            # Check if we got valid XML/RSS content
            content_type = response.headers.get('content-type', '').lower()
            if 'xml' in content_type or 'rss' in content_type or 'text' in content_type:
                feed = feedparser.parse(response.content)
                if feed.entries:
                    logger.info(f"Successfully fetched {len(feed.entries)} entries from {source_name} via requests")
                    return feed
            
            # Method 2: Try direct feedparser
            feed = feedparser.parse(feed_url)
            if feed.entries:
                logger.info(f"Successfully fetched {len(feed.entries)} entries from {source_name} via feedparser")
                return feed
                
        except requests.RequestException as e:
            logger.debug(f"Attempt {attempt + 1} failed for {source_name}: {e}")
            time.sleep(1)  # Brief delay before retry
        except Exception as e:
            logger.debug(f"Attempt {attempt + 1} failed for {source_name}: {e}")
            time.sleep(1)
    
    return None

def scrape_archive_page(url: str, source_name: str) -> List[Dict[str, Any]]:
    """
    Scrape news headlines from archive/news pages (non-RSS).
    
    Args:
        url: Archive page URL
        source_name: Name of the source
        
    Returns:
        List of headline dictionaries
    """
    headlines = []
    
    try:
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache'
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Common patterns for news headlines
        headline_selectors = [
            'h1', 'h2', 'h3', 'h4',  # Headers
            '.headline', '.title', '.article-title',  # Common classes
            'a[href*="/news/"]', 'a[href*="/story/"]',  # News links
            '.story-title', '.article-headline',  # More specific classes
            '.entry-title', '.post-title',  # Blog/WordPress classes
            'a[href*="/article/"]', 'a[href*="/analysis/"]',  # Article links
            '.news-title', '.content-title',  # News specific classes
            'h3 a', 'h4 a',  # Headers with links
            '.teaser-title', '.card-title',  # Card/teaser titles
        ]
        
        for selector in headline_selectors:
            elements = soup.select(selector)
            for element in elements[:15]:  # Reduced limit for quality focus
                title = clean_text(element.get_text())
                link = element.get('href', '')
                
                # Make relative URLs absolute
                if link.startswith('/'):
                    link = urljoin(url, link)
                
                if title and len(title) > 10 and is_football_related(title, ''):
                    headline = {
                        'title': title,
                        'summary': '',
                        'link': link,
                        'source': f"{source_name}_archive",
                        'published': datetime.now().isoformat(),
                        'raw_content': ''
                    }
                    headlines.append(headline)
        
        logger.info(f"Scraped {len(headlines)} headlines from {source_name} archive")
        
    except Exception as e:
        logger.error(f"Error scraping {source_name} archive: {e}")
    
    return headlines

def fetch_headlines(max_age_hours: int = 720) -> List[Dict[str, Any]]:
    """
    Enhanced fetch headlines from all configured RSS feeds and archive pages.
    Final quality-focused version with rule-based filtering.
    
    Args:
        max_age_hours: Only fetch headlines from the last N hours (default: 720 = 30 days)
        
    Returns:
        List of headline dictionaries
    """
    all_headlines = []
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    # Fetch from RSS feeds
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            logger.info(f"Fetching headlines from {source_name}...")
            
            feed = fetch_rss_feed(feed_url, source_name)
            
            if not feed or not feed.entries:
                logger.warning(f"No entries found for {source_name}")
                continue
            
            if feed.bozo:
                logger.warning(f"Feed parsing error for {source_name}: {feed.bozo_exception}")
                
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
                
                # Assess quality using rule-based approach
                quality_assessment = assess_headline_quality(title, summary)
                
                # Only include high-quality headlines with player names
                if quality_assessment.get('is_high_quality', False) and quality_assessment.get('has_player_name', False):
                    headline = {
                        'title': title,
                        'summary': summary,
                        'link': entry.get('link', ''),
                        'source': source_name,
                        'published': datetime.fromtimestamp(pub_time).isoformat(),
                        'raw_content': clean_text(entry.get('content', [{}])[0].get('value', '')) if entry.get('content') else '',
                        'quality_score': quality_assessment.get('relevance_score', 5),
                        'player_names': quality_assessment.get('player_names', []),
                        'quality_reason': quality_assessment.get('reason', '')
                    }
                    
                    all_headlines.append(headline)
                    football_headlines += 1
                
            logger.info(f"Fetched {football_headlines}/{total_headlines} quality football headlines from {source_name}")
            
        except Exception as e:
            logger.error(f"Error fetching from {source_name}: {str(e)}")
            continue
    
    # Fetch from archive pages
    logger.info("Fetching from archive pages...")
    for source_name, archive_url in ARCHIVE_SOURCES.items():
        try:
            archive_headlines = scrape_archive_page(archive_url, source_name)
            
            # Quality filter archive headlines
            quality_archive_headlines = []
            for headline in archive_headlines:
                quality_assessment = assess_headline_quality(headline['title'], headline['summary'])
                
                if quality_assessment.get('is_high_quality', False) and quality_assessment.get('has_player_name', False):
                    headline['quality_score'] = quality_assessment.get('relevance_score', 5)
                    headline['player_names'] = quality_assessment.get('player_names', [])
                    headline['quality_reason'] = quality_assessment.get('reason', '')
                    quality_archive_headlines.append(headline)
            
            all_headlines.extend(quality_archive_headlines)
            logger.info(f"Added {len(quality_archive_headlines)} quality headlines from {source_name} archive")
            
        except Exception as e:
            logger.error(f"Error fetching from {source_name} archive: {e}")
            continue
    
    # Remove duplicates based on title similarity
    unique_headlines = []
    seen_titles = set()
    
    for headline in all_headlines:
        title_lower = headline['title'].lower()
        # Check for similar titles (allowing for minor variations)
        is_duplicate = False
        for seen_title in seen_titles:
            if title_lower in seen_title or seen_title in title_lower:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_headlines.append(headline)
            seen_titles.add(title_lower)
    
    # Sort by quality score and publication date (highest quality first)
    unique_headlines.sort(key=lambda x: (x.get('quality_score', 5), x['published']), reverse=True)
    
    logger.info(f"Total quality football headlines fetched: {len(unique_headlines)}")
    return unique_headlines

def save_headlines(headlines: List[Dict[str, Any]], output_file: str = 'news/final_quality_headlines.json') -> None:
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
            'date_range': f"Last {len(headlines)} quality football headlines from various sources",
            'quality_focus': 'Headlines filtered for player names and high relevance'
        },
        'headlines': headlines
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(headlines)} quality football headlines to {output_file}")

def main():
    """Final quality-focused main function to fetch and save headlines."""
    logger.info("Starting final quality-focused fantasy football news headline fetch...")
    
    # Fetch headlines from the last 30 days (720 hours) for more comprehensive coverage
    headlines = fetch_headlines(max_age_hours=720)
    
    if headlines:
        save_headlines(headlines)
        logger.info("Final quality-focused news fetch completed successfully!")
        
        # Print a detailed summary of what was fetched
        print(f"\n=== FINAL QUALITY-FOCUSED FETCH SUMMARY ===")
        print(f"Total quality football headlines: {len(headlines)}")
        
        # Group by source for better analysis
        source_counts = {}
        for headline in headlines:
            source = headline['source']
            source_counts[source] = source_counts.get(source, 0) + 1
        
        print(f"Sources and counts:")
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count} headlines")
        
        print(f"Date range: {headlines[-1]['published'][:10]} to {headlines[0]['published'][:10]}")
        print(f"\nTop quality headlines:")
        for i, headline in enumerate(headlines[:15]):  # Show top 15
            quality_score = headline.get('quality_score', 5)
            player_names = headline.get('player_names', [])
            print(f"{i+1}. [{quality_score}/10] {headline['title'][:70]}... ({headline['source']})")
            if player_names:
                print(f"    Players: {', '.join(player_names)}")
        
        # Show some statistics
        print(f"\n=== QUALITY STATISTICS ===")
        avg_quality = sum(h.get('quality_score', 5) for h in headlines) / len(headlines)
        print(f"Average quality score: {avg_quality:.1f}/10")
        print(f"Headlines with player names: {len([h for h in headlines if h.get('player_names')])}")
        print(f"Sources with archive scraping: {len([s for s in source_counts.keys() if 'archive' in s])}")
        print(f"RSS-only sources: {len([s for s in source_counts.keys() if 'archive' not in s])}")
        
    else:
        logger.warning("No quality football headlines were fetched. Check RSS feed URLs and connectivity.")

if __name__ == "__main__":
    main() 
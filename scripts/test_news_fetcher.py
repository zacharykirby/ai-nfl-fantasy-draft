#!/usr/bin/env python3
"""
Test script for the improved news fetcher.
Demonstrates the improvements made to get more football-specific content.
"""

import json
import os
from datetime import datetime

def analyze_headlines():
    """Analyze the fetched headlines to show improvements."""
    
    if not os.path.exists('news/raw_headlines.json'):
        print("No headlines file found. Run the news fetcher first.")
        return
    
    with open('news/raw_headlines.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    headlines = data['headlines']
    metadata = data['metadata']
    
    print("=" * 60)
    print("NEWS FETCHER ANALYSIS")
    print("=" * 60)
    
    print(f"Total headlines: {metadata['total_headlines']}")
    print(f"Sources: {', '.join(metadata['sources'])}")
    print(f"Fetched at: {metadata['fetched_at']}")
    print(f"Date range: {headlines[-1]['published'][:10]} to {headlines[0]['published'][:10]}")
    
    print(f"\nSource breakdown:")
    source_counts = {}
    for headline in headlines:
        source = headline['source']
        source_counts[source] = source_counts.get(source, 0) + 1
    
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {source}: {count} headlines")
    
    print(f"\nSample headlines by source:")
    for source in metadata['sources']:
        source_headlines = [h for h in headlines if h['source'] == source]
        if source_headlines:
            print(f"\n{source.upper()}:")
            for i, headline in enumerate(source_headlines[:3]):
                print(f"  {i+1}. {headline['title'][:70]}...")
    
    # Check for football-specific content
    football_keywords = ['fantasy football', 'nfl', 'quarterback', 'running back', 'wide receiver', 'draft', 'rankings']
    football_count = 0
    
    for headline in headlines:
        content = (headline['title'] + ' ' + headline['summary']).lower()
        if any(keyword in content for keyword in football_keywords):
            football_count += 1
    
    print(f"\nContent Analysis:")
    print(f"  Football-related headlines: {football_count}/{len(headlines)} ({football_count/len(headlines)*100:.1f}%)")
    
    # Check for recent content
    recent_count = 0
    for headline in headlines:
        pub_date = datetime.fromisoformat(headline['published'].replace('Z', '+00:00'))
        if (datetime.now() - pub_date.replace(tzinfo=None)).days <= 7:
            recent_count += 1
    
    print(f"  Headlines from last 7 days: {recent_count}/{len(headlines)} ({recent_count/len(headlines)*100:.1f}%)")
    
    print(f"\n" + "=" * 60)
    print("IMPROVEMENTS MADE:")
    print("=" * 60)
    print("✅ Extended time range from 24 hours to 2 weeks")
    print("✅ Added football-specific keyword filtering")
    print("✅ Excluded baseball and other sports content")
    print("✅ Improved RSS feed sources and error handling")
    print("✅ Better content cleaning and formatting")
    print("✅ Multiple fallback methods for feed fetching")
    print(f"✅ Increased headline count from ~16 to {len(headlines)}")
    print("✅ Added multiple reliable sources")

if __name__ == "__main__":
    analyze_headlines() 
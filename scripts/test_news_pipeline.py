#!/usr/bin/env python3
"""
Test script for the news pipeline.

This script tests the RSS fetching and Ollama analysis functionality.
"""

import json
import logging
import os
import sys
from datetime import datetime

# Add scripts directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from news_fetcher import fetch_headlines, save_headlines
from news_analyzer import setup_ollama_client, analyze_headline, create_analysis_prompt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_rss_fetching():
    """Test RSS feed fetching functionality."""
    logger.info("Testing RSS feed fetching...")
    
    try:
        # Fetch a small number of headlines for testing
        headlines = fetch_headlines(max_age_hours=48)
        
        if headlines:
            logger.info(f"✅ Successfully fetched {len(headlines)} headlines")
            
            # Save to test file
            save_headlines(headlines, 'news/test_headlines.json')
            logger.info("✅ Saved test headlines to news/test_headlines.json")
            
            # Show sample headlines
            logger.info("Sample headlines:")
            for i, headline in enumerate(headlines[:3]):
                logger.info(f"  {i+1}. {headline['title'][:80]}...")
                logger.info(f"     Source: {headline['source']}")
                logger.info(f"     Published: {headline['published']}")
                logger.info("")
            
            return True
        else:
            logger.error("❌ No headlines fetched")
            return False
            
    except Exception as e:
        logger.error(f"❌ RSS fetching failed: {str(e)}")
        return False

def test_ollama_connection():
    """Test Ollama connection and basic functionality."""
    logger.info("Testing Ollama connection...")
    
    try:
        client = setup_ollama_client()
        if client:
            logger.info("✅ Ollama connection successful")
            return True
        else:
            logger.error("❌ Ollama connection failed")
            return False
    except Exception as e:
        logger.error(f"❌ Ollama test failed: {str(e)}")
        return False

def test_headline_analysis():
    """Test headline analysis with a sample headline."""
    logger.info("Testing headline analysis...")
    
    # Sample test headline
    test_headline = {
        'title': 'De\'Von Achane expected to be full participant in training camp',
        'summary': 'Miami Dolphins running back De\'Von Achane is expected to be a full participant when training camp begins next week.',
        'source': 'test',
        'published': datetime.now().isoformat(),
        'link': 'https://example.com'
    }
    
    try:
        client = setup_ollama_client()
        if not client:
            logger.error("❌ Cannot test analysis without Ollama connection")
            return False
        
        # Test the prompt creation
        prompt = create_analysis_prompt(test_headline['title'], test_headline['summary'])
        logger.info("✅ Prompt creation successful")
        
        # Test the analysis
        analysis = analyze_headline(client, test_headline)
        if analysis:
            logger.info("✅ Headline analysis successful")
            logger.info(f"Player: {analysis.get('player', 'N/A')}")
            logger.info(f"Sentiment: {analysis.get('sentiment_score', 'N/A')}")
            logger.info(f"Buzz: {analysis.get('buzz_score', 'N/A')}")
            logger.info(f"Injury: {analysis.get('injury_flag', 'N/A')}")
            return True
        else:
            logger.error("❌ Headline analysis failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Analysis test failed: {str(e)}")
        return False

def test_raw_ollama_response():
    """Test raw Ollama response to see what we're getting."""
    logger.info("Testing raw Ollama response...")
    
    try:
        client = setup_ollama_client()
        if not client:
            logger.error("❌ Cannot test without Ollama connection")
            return False
        
        # Simple test prompt
        test_prompt = "Return a JSON object with a single key 'test' set to 'success'"
        
        logger.info("Sending test prompt to Ollama...")
        response = client.chat(
            model='deepseek-r1:14b',
            messages=[{'role': 'user', 'content': test_prompt}],
            options={'temperature': 0.1}
        )
        
        content = response['message']['content'].strip()
        logger.info(f"Raw response length: {len(content)}")
        logger.info(f"Raw response: '{content}'")
        
        if content:
            logger.info("✅ Got non-empty response from Ollama")
            return True
        else:
            logger.error("❌ Got empty response from Ollama")
            return False
            
    except Exception as e:
        logger.error(f"❌ Raw response test failed: {str(e)}")
        return False

def test_full_pipeline():
    """Test the complete pipeline with a few headlines."""
    logger.info("Testing full pipeline...")
    
    try:
        # Fetch a few headlines
        headlines = fetch_headlines(max_age_hours=48)
        if not headlines:
            logger.error("❌ No headlines to test with")
            return False
        
        # Limit to first 3 headlines for testing
        test_headlines = headlines[:3]
        logger.info(f"Testing with {len(test_headlines)} headlines")
        
        # Setup Ollama
        client = setup_ollama_client()
        if not client:
            logger.error("❌ Cannot test pipeline without Ollama connection")
            return False
        
        # Analyze each headline
        analyses = []
        for i, headline in enumerate(test_headlines):
            logger.info(f"Analyzing test headline {i+1}/{len(test_headlines)}...")
            analysis = analyze_headline(client, headline)
            if analysis:
                analyses.append(analysis)
                logger.info(f"  ✅ Analyzed: {analysis.get('player', 'Unknown')}")
            else:
                logger.warning(f"  ⚠️ Failed to analyze headline {i+1}")
        
        if analyses:
            logger.info(f"✅ Successfully analyzed {len(analyses)} headlines")
            
            # Save test results
            test_output = {
                'metadata': {
                    'test_run_at': datetime.now().isoformat(),
                    'headlines_tested': len(test_headlines),
                    'successful_analyses': len(analyses)
                },
                'analyses': analyses
            }
            
            with open('news/test_analysis.json', 'w', encoding='utf-8') as f:
                json.dump(test_output, f, indent=2, ensure_ascii=False)
            
            logger.info("✅ Saved test analysis to news/test_analysis.json")
            return True
        else:
            logger.error("❌ No successful analyses")
            return False
            
    except Exception as e:
        logger.error(f"❌ Full pipeline test failed: {str(e)}")
        return False

def main():
    """Run all tests."""
    logger.info("Starting news pipeline tests...")
    
    tests = [
        ("RSS Fetching", test_rss_fetching),
        ("Ollama Connection", test_ollama_connection),
        ("Raw Ollama Response", test_raw_ollama_response),
        ("Headline Analysis", test_headline_analysis),
        ("Full Pipeline", test_full_pipeline)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("🎉 All tests passed! The news pipeline is ready to use.")
    else:
        logger.error("⚠️ Some tests failed. Check the logs above for details.")

if __name__ == "__main__":
    main() 
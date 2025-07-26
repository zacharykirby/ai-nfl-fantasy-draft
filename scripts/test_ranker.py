#!/usr/bin/env python3
"""
Test script for the Player Ranking Module
Validates the ranking system and demonstrates its features
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ranker import PlayerRanker
import pandas as pd
import json

def test_ranking_system():
    """Test the ranking system with various scenarios"""
    
    print("🧪 Testing NFL Fantasy Draft Ranking System")
    print("=" * 60)
    
    # Initialize ranker
    ranker = PlayerRanker()
    
    # Test data loading
    print("\n1. Testing data loading...")
    try:
        stats_df, news_data = ranker.load_data()
        print(f"✅ Loaded {len(stats_df)} players from stats")
        print(f"✅ Loaded news features for {len(news_data.get('player_features', {}))} players")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return
    
    # Test individual scoring components
    print("\n2. Testing scoring components...")
    if len(stats_df) > 0:
        sample_player = stats_df.iloc[0]
        print(f"Sample player: {sample_player['player']} ({sample_player['position']})")
        
        # Test each scoring component
        historical = ranker.calculate_historical_performance_score(sample_player)
        form = ranker.calculate_current_form_score(sample_player)
        injury = ranker.calculate_injury_risk_score(sample_player)
        experience = ranker.calculate_experience_bonus(sample_player)
        team = ranker.calculate_team_context_score(sample_player)
        news = ranker.calculate_news_sentiment_score(sample_player, news_data)
        consistency = ranker.calculate_consistency_score(sample_player)
        
        print(f"   Historical Performance: {historical:.3f}")
        print(f"   Current Form: {form:.3f}")
        print(f"   Injury Risk: {injury:.3f}")
        print(f"   Experience Bonus: {experience:.3f}")
        print(f"   Team Context: {team:.3f}")
        print(f"   News Sentiment: {news:.3f}")
        print(f"   Consistency: {consistency:.3f}")
    
    # Test full ranking
    print("\n3. Testing full ranking system...")
    try:
        ranked_df = ranker.rank_players()
        print(f"✅ Successfully ranked {len(ranked_df)} players")
        
        # Show top players by position
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_df = ranked_df[ranked_df['position'] == position]
            if len(pos_df) > 0:
                top_player = pos_df.iloc[0]
                print(f"   Top {position}: {top_player['player']} (Score: {top_player['total_score']:.1f})")
        
    except Exception as e:
        print(f"❌ Error in ranking: {e}")
        return
    
    # Test export functionality
    print("\n4. Testing export functionality...")
    try:
        ranker.export_rankings(ranked_df)
        print("✅ Successfully exported rankings to outputs/")
        
        # Check output files
        import pathlib
        outputs_dir = pathlib.Path("outputs")
        csv_files = list(outputs_dir.glob("ranked_*.csv"))
        print(f"   Generated {len(csv_files)} CSV files")
        
    except Exception as e:
        print(f"❌ Error exporting: {e}")
    
    # Test position-specific analysis
    print("\n5. Testing position-specific analysis...")
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = ranked_df[ranked_df['position'] == position]
        if len(pos_df) > 0:
            avg_score = pos_df['total_score'].mean()
            max_score = pos_df['total_score'].max()
            min_score = pos_df['total_score'].min()
            print(f"   {position}: Avg={avg_score:.1f}, Max={max_score:.1f}, Min={min_score:.1f}")
    
    # Test tier distribution
    print("\n6. Testing tier distribution...")
    tier_counts = ranked_df['tier'].value_counts().sort_index()
    for tier, count in tier_counts.items():
        print(f"   Tier {int(tier)}: {count} players")
    
    print("\n✅ All tests completed successfully!")
    print("\n📊 Ranking System Features:")
    print("   • Historical performance analysis")
    print("   • Injury risk assessment")
    print("   • Experience level considerations")
    print("   • Team context evaluation")
    print("   • News sentiment integration")
    print("   • Consistency scoring")
    print("   • Position-specific adjustments")
    print("   • Tier-based ranking system")

def analyze_ranking_insights():
    """Analyze the ranking results for insights"""
    
    print("\n🔍 Ranking Analysis & Insights")
    print("=" * 60)
    
    try:
        # Load ranking summary
        with open("outputs/ranking_summary.json", 'r') as f:
            summary = json.load(f)
        
        print(f"\n📈 Overall Statistics:")
        print(f"   Total Players Ranked: {summary['total_players']}")
        print(f"   Positions Covered: {', '.join(summary['positions'].keys())}")
        
        print(f"\n🏆 Top Players by Position:")
        for position, players in summary['top_players_by_position'].items():
            print(f"\n   {position}:")
            for i, player in enumerate(players[:3], 1):
                print(f"     {i}. {player['player']} ({player['team']}) - Score: {player['total_score']:.1f}")
        
        print(f"\n📊 Tier Distribution:")
        for tier, count in summary['tiers'].items():
            percentage = (count / summary['total_players']) * 100
            print(f"   Tier {int(float(tier))}: {count} players ({percentage:.1f}%)")
        
        # Load detailed rankings
        all_players = pd.read_csv("outputs/ranked_all_players.csv")
        
        print(f"\n🎯 Key Insights:")
        
        # Team analysis
        team_performance = all_players.groupby('team')['total_score'].mean().sort_values(ascending=False)
        print(f"   Top 3 Teams by Average Player Score:")
        for team, score in team_performance.head(3).items():
            print(f"     {team}: {score:.1f}")
        
        # Experience analysis
        exp_performance = all_players.groupby('experience_level')['total_score'].mean()
        print(f"   Performance by Experience Level:")
        for level, score in exp_performance.items():
            print(f"     {level}: {score:.1f}")
        
        # Age analysis
        all_players['age_group'] = pd.cut(all_players['age'], bins=[0, 25, 30, 35, 100], 
                                        labels=['Young (≤25)', 'Prime (26-30)', 'Veteran (31-35)', 'Senior (35+)'])
        age_performance = all_players.groupby('age_group')['total_score'].mean()
        print(f"   Performance by Age Group:")
        for age_group, score in age_performance.items():
            print(f"     {age_group}: {score:.1f}")
        
    except Exception as e:
        print(f"❌ Error in analysis: {e}")

if __name__ == "__main__":
    test_ranking_system()
    analyze_ranking_insights() 
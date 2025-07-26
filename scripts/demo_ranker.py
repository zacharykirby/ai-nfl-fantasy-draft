#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Ranking System Demo
Demonstrates practical usage of the player ranking system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ranker import PlayerRanker
import pandas as pd

def demo_basic_ranking():
    """Demonstrate basic ranking functionality"""
    print("🏈 NFL Fantasy Draft Assistant - Ranking Demo")
    print("=" * 60)
    
    # Initialize ranker
    ranker = PlayerRanker()
    
    # Generate rankings
    print("\n📊 Generating player rankings...")
    ranked_df = ranker.rank_players()
    
    # Show top players by position
    print("\n🏆 Top 3 Players by Position:")
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = ranked_df[ranked_df['position'] == position]
        if len(pos_df) > 0:
            print(f"\n{position}:")
            for i, (_, player) in enumerate(pos_df.head(3).iterrows(), 1):
                print(f"  {i}. {player['player']} ({player['team']}) - Score: {player['total_score']:.1f}")
    
    return ranked_df

def demo_position_analysis(ranked_df):
    """Demonstrate position-specific analysis"""
    print("\n📈 Position Analysis:")
    print("-" * 40)
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = ranked_df[ranked_df['position'] == position]
        if len(pos_df) > 0:
            avg_score = pos_df['total_score'].mean()
            max_score = pos_df['total_score'].max()
            min_score = pos_df['total_score'].min()
            std_score = pos_df['total_score'].std()
            
            print(f"\n{position} Statistics:")
            print(f"  Average Score: {avg_score:.1f}")
            print(f"  Score Range: {min_score:.1f} - {max_score:.1f}")
            print(f"  Standard Deviation: {std_score:.1f}")
            print(f"  Players Ranked: {len(pos_df)}")

def demo_team_analysis(ranked_df):
    """Demonstrate team-based analysis"""
    print("\n🏈 Team Performance Analysis:")
    print("-" * 40)
    
    # Team average scores
    team_scores = ranked_df.groupby('team')['total_score'].agg(['mean', 'count']).sort_values('mean', ascending=False)
    
    print("\nTop 5 Teams by Average Player Score:")
    for team, (avg_score, count) in team_scores.head(5).iterrows():
        print(f"  {team}: {avg_score:.1f} (avg) - {count} players")
    
    print("\nBottom 5 Teams by Average Player Score:")
    for team, (avg_score, count) in team_scores.tail(5).iterrows():
        print(f"  {team}: {avg_score:.1f} (avg) - {count} players")

def demo_experience_analysis(ranked_df):
    """Demonstrate experience level analysis"""
    print("\n👴 Experience Level Analysis:")
    print("-" * 40)
    
    # Experience level performance
    exp_scores = ranked_df.groupby('experience_level')['total_score'].agg(['mean', 'count'])
    
    print("\nPerformance by Experience Level:")
    for level, (avg_score, count) in exp_scores.iterrows():
        print(f"  {level}: {avg_score:.1f} (avg) - {count} players")
    
    # Age analysis
    print("\nAge Distribution:")
    age_groups = pd.cut(ranked_df['age'], bins=[0, 25, 30, 35, 100], 
                       labels=['Young (≤25)', 'Prime (26-30)', 'Veteran (31-35)', 'Senior (35+)'])
    age_scores = ranked_df.groupby(age_groups)['total_score'].agg(['mean', 'count'])
    
    for age_group, (avg_score, count) in age_scores.iterrows():
        if pd.notna(age_group):
            print(f"  {age_group}: {avg_score:.1f} (avg) - {count} players")

def demo_tier_analysis(ranked_df):
    """Demonstrate tier-based analysis"""
    print("\n⭐ Tier Analysis:")
    print("-" * 40)
    
    # Tier distribution
    tier_counts = ranked_df['tier'].value_counts().sort_index()
    total_players = len(ranked_df)
    
    print("\nTier Distribution:")
    for tier, count in tier_counts.items():
        percentage = (count / total_players) * 100
        print(f"  Tier {int(tier)}: {count} players ({percentage:.1f}%)")
    
    # Show tier 1 players
    tier1_players = ranked_df[ranked_df['tier'] == 1.0]
    print(f"\nTier 1 Players ({len(tier1_players)} total):")
    for _, player in tier1_players.iterrows():
        print(f"  {player['player']} ({player['position']}, {player['team']}) - Score: {player['total_score']:.1f}")

def demo_custom_filters(ranked_df):
    """Demonstrate custom filtering capabilities"""
    print("\n🔍 Custom Filter Examples:")
    print("-" * 40)
    
    # High-scoring veterans
    veterans = ranked_df[(ranked_df['experience_level'] == 'Veteran') & (ranked_df['total_score'] > 60)]
    print(f"\nHigh-Scoring Veterans (Score > 60):")
    for _, player in veterans.iterrows():
        print(f"  {player['player']} ({player['position']}, {player['team']}) - Score: {player['total_score']:.1f}")
    
    # Young players with potential
    young_players = ranked_df[(ranked_df['age'] <= 25) & (ranked_df['total_score'] > 50)]
    print(f"\nYoung Players with Potential (Age ≤ 25, Score > 50):")
    for _, player in young_players.iterrows():
        print(f"  {player['player']} ({player['position']}, {player['team']}) - Age: {player['age']}, Score: {player['total_score']:.1f}")
    
    # Elite team players
    elite_teams = ['KC', 'SF', 'BAL', 'BUF', 'DAL', 'PHI']
    elite_players = ranked_df[ranked_df['team'].isin(elite_teams)]
    print(f"\nElite Team Players:")
    for _, player in elite_players.iterrows():
        print(f"  {player['player']} ({player['position']}, {player['team']}) - Score: {player['total_score']:.1f}")

def demo_export_options(ranked_df):
    """Demonstrate export functionality"""
    print("\n💾 Export Options:")
    print("-" * 40)
    
    # Export rankings
    ranker = PlayerRanker()
    ranker.export_rankings(ranked_df)
    
    print("✅ Rankings exported to outputs/ directory:")
    print("  - ranked_all_players.csv (complete rankings)")
    print("  - ranked_QB.csv (quarterback rankings)")
    print("  - ranked_RB.csv (running back rankings)")
    print("  - ranked_WR.csv (wide receiver rankings)")
    print("  - ranked_TE.csv (tight end rankings)")
    print("  - ranking_summary.json (comprehensive summary)")

def main():
    """Main demonstration function"""
    try:
        # Run basic ranking demo
        ranked_df = demo_basic_ranking()
        
        # Run analysis demos
        demo_position_analysis(ranked_df)
        demo_team_analysis(ranked_df)
        demo_experience_analysis(ranked_df)
        demo_tier_analysis(ranked_df)
        demo_custom_filters(ranked_df)
        demo_export_options(ranked_df)
        
        print("\n🎉 Demo completed successfully!")
        print("\n💡 Key Takeaways:")
        print("  • The ranking system provides comprehensive player evaluation")
        print("  • Position-specific adjustments ensure fair comparisons")
        print("  • Team context significantly impacts player scores")
        print("  • Experience and age factors are carefully balanced")
        print("  • Multiple export formats support various use cases")
        
    except Exception as e:
        print(f"❌ Error in demo: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 
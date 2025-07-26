#!/usr/bin/env python3
"""
Test script to verify the data quality and show insights from the NFL data.
"""

import pandas as pd
import json
from pathlib import Path

def test_data_quality():
    """Test the quality of the ingested data."""
    
    # Load the data
    data_path = Path("data/nfl_player_data.csv")
    if not data_path.exists():
        print("❌ Data file not found. Run data_ingest.py first.")
        return
    
    df = pd.read_csv(data_path)
    
    print("📊 NFL Fantasy Data Quality Report")
    print("=" * 50)
    
    # Basic statistics
    print(f"Total players: {len(df)}")
    print(f"Seasons: {sorted(df['season'].unique())}")
    print(f"Positions: {df['position'].value_counts().to_dict()}")
    
    # Check for missing data
    print(f"\nMissing data analysis:")
    missing_data = df.isnull().sum()
    missing_data = missing_data[missing_data > 0]
    if len(missing_data) > 0:
        for col, count in missing_data.items():
            percentage = (count / len(df)) * 100
            print(f"  {col}: {count} ({percentage:.1f}%)")
    else:
        print("  No missing data found!")
    
    # Fantasy points analysis
    if 'total_fantasy_points' in df.columns:
        print(f"\nFantasy Points Analysis:")
        print(f"  Average: {df['total_fantasy_points'].mean():.2f}")
        print(f"  Median: {df['total_fantasy_points'].median():.2f}")
        print(f"  Max: {df['total_fantasy_points'].max():.2f}")
        print(f"  Min: {df['total_fantasy_points'].min():.2f}")
    
    # Top performers by position
    print(f"\nTop 5 Players by Position (2023):")
    df_2023 = df[df['season'] == 2023].copy()
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df_2023[df_2023['position'] == position].copy()
        if len(pos_df) > 0:
            top_players = pos_df.nlargest(5, 'total_fantasy_points')
            print(f"\n{position}:")
            for _, player in top_players.iterrows():
                name = player.get('player_name', 'Unknown')
                points = player.get('total_fantasy_points', 0)
                team = player.get('team', 'Unknown')
                print(f"  {name} ({team}): {points:.1f} points")
    
    # Consistency analysis
    if 'consistency_score' in df.columns:
        print(f"\nMost Consistent Players (2023):")
        consistent_players = df_2023.nlargest(10, 'consistency_score')
        for _, player in consistent_players.iterrows():
            name = player.get('player_name', 'Unknown')
            consistency = player.get('consistency_score', 0)
            position = player.get('position', 'Unknown')
            print(f"  {name} ({position}): {consistency:.2f}")

def show_data_structure():
    """Show the structure of the data."""
    
    data_path = Path("data/nfl_player_data.csv")
    if not data_path.exists():
        print("❌ Data file not found. Run data_ingest.py first.")
        return
    
    df = pd.read_csv(data_path)
    
    print("📋 Data Structure Analysis")
    print("=" * 50)
    
    # Column categories
    passing_cols = [col for col in df.columns if 'passing' in col.lower()]
    rushing_cols = [col for col in df.columns if 'rushing' in col.lower()]
    receiving_cols = [col for col in df.columns if 'receiving' in col.lower()]
    fantasy_cols = [col for col in df.columns if 'fantasy' in col.lower()]
    combine_cols = [col for col in df.columns if col in ['forty', 'bench', 'vertical', 'broad_jump', 'three_cone', 'shuttle']]
    
    print(f"Passing statistics: {len(passing_cols)} columns")
    print(f"Rushing statistics: {len(rushing_cols)} columns")
    print(f"Receiving statistics: {len(receiving_cols)} columns")
    print(f"Fantasy metrics: {len(fantasy_cols)} columns")
    print(f"Combine metrics: {len(combine_cols)} columns")
    
    print(f"\nTotal columns: {len(df.columns)}")
    print(f"Sample columns: {df.columns[:10].tolist()}")

if __name__ == "__main__":
    print("🧪 Testing NFL Data Ingestion Results")
    print("=" * 50)
    
    test_data_quality()
    print("\n" + "=" * 50)
    show_data_structure()
    
    print(f"\n✅ Data quality test completed!") 
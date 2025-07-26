#!/usr/bin/env python3
"""
Quick script to show 2024 season top performers.
"""

import pandas as pd

def show_2024_top_performers():
    """Show top performers from the 2024 season."""
    
    # Load the data
    df = pd.read_csv('data/nfl_player_data.csv')
    df_2024 = df[df['season'] == 2024].copy()
    
    print("🏈 2024 Season Top Performers")
    print("=" * 50)
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df_2024[df_2024['position'] == position].copy()
        if len(pos_df) > 0:
            top_players = pos_df.nlargest(5, 'total_fantasy_points')
            print(f"\n{position}:")
            for _, player in top_players.iterrows():
                name = player.get('player_name', 'Unknown')
                points = player.get('total_fantasy_points', 0)
                team = player.get('team', 'Unknown')
                print(f"  {name} ({team}): {points:.1f} points")
    
    # Show some overall stats
    print(f"\n📊 2024 Season Summary:")
    print(f"  Total players: {len(df_2024)}")
    print(f"  Average fantasy points: {df_2024['total_fantasy_points'].mean():.1f}")
    print(f"  Max fantasy points: {df_2024['total_fantasy_points'].max():.1f}")
    print(f"  Position breakdown:")
    for pos, count in df_2024['position'].value_counts().items():
        if pos != 'Unknown':
            print(f"    {pos}: {count} players")

if __name__ == "__main__":
    show_2024_top_performers() 
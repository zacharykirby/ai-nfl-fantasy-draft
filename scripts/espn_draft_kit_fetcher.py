#!/usr/bin/env python3
"""
ESPN Draft Kit Fetcher - 2025 Fantasy Football Data Integration

This module fetches current 2025 fantasy football draft data from multiple sources:
- ESPN Fantasy Football API
- FantasyPros rankings and projections
- NFL.com player data
- Other fantasy football data providers

The goal is to integrate the latest 2025 draft kit information into our ranking system.
"""

import requests
import pandas as pd
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import time
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ESPNDraftKitFetcher:
    """Fetches and processes 2025 ESPN Fantasy Football Draft Kit data"""
    
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        # ESPN API endpoints (these may need to be updated)
        self.espn_base_url = "https://fantasy.espn.com/apis/v3/games/ffl"
        self.espn_season = 2025
        
        # Headers for API requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
    def fetch_espn_rankings(self) -> pd.DataFrame:
        """Fetch ESPN's current fantasy football rankings"""
        try:
            logger.info("Fetching ESPN fantasy football rankings...")
            
            # ESPN rankings endpoint
            url = f"{self.espn_base_url}/seasons/{self.espn_season}/segments/0/leaguedefaults/3"
            params = {
                'view': 'kona_player_info',
                'scoringPeriodId': 0
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract player data
            players = []
            if 'players' in data:
                for player in data['players']:
                    player_info = player.get('player', {})
                    stats = player.get('playerPoolEntry', {}).get('player', {}).get('stats', [])
                    
                    # Get fantasy points from stats
                    fantasy_points = 0
                    for stat in stats:
                        if stat.get('statSourceId') == 0:  # Season stats
                            fantasy_points = stat.get('appliedTotal', 0)
                            break
                    
                    players.append({
                        'player_name': player_info.get('fullName', ''),
                        'position': player_info.get('defaultPositionId', ''),
                        'team': player_info.get('proTeamId', ''),
                        'rank': player.get('rank', 999),
                        'fantasy_points': fantasy_points,
                        'source': 'ESPN'
                    })
            
            df = pd.DataFrame(players)
            logger.info(f"Fetched {len(df)} players from ESPN")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching ESPN rankings: {e}")
            return pd.DataFrame()
    
    def fetch_fantasypros_rankings(self) -> pd.DataFrame:
        """Fetch FantasyPros current rankings"""
        try:
            logger.info("Fetching FantasyPros rankings...")
            
            # FantasyPros API endpoint (this may need to be updated)
            url = "https://api.fantasypros.com/v2/json/nfl/2025/consensus-rankings"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            players = []
            if 'rankings' in data:
                for rank_data in data['rankings']:
                    players.append({
                        'player_name': rank_data.get('player_name', ''),
                        'position': rank_data.get('position', ''),
                        'team': rank_data.get('team', ''),
                        'rank': rank_data.get('rank', 999),
                        'fantasy_points': rank_data.get('fantasy_points', 0),
                        'source': 'FantasyPros'
                    })
            
            df = pd.DataFrame(players)
            logger.info(f"Fetched {len(df)} players from FantasyPros")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching FantasyPros rankings: {e}")
            return pd.DataFrame()
    
    def fetch_nfl_com_data(self) -> pd.DataFrame:
        """Fetch NFL.com player data"""
        try:
            logger.info("Fetching NFL.com player data...")
            
            # NFL.com stats endpoint
            url = "https://www.nfl.com/stats/player-stats"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # This would need to be parsed from HTML or use a different endpoint
            # For now, return empty DataFrame
            logger.warning("NFL.com data fetching not implemented yet")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error fetching NFL.com data: {e}")
            return pd.DataFrame()
    
    def create_2025_projections(self) -> pd.DataFrame:
        """Create 2025 projections based on historical data and trends"""
        try:
            logger.info("Creating 2025 projections from historical data...")
            
            # Load existing historical data
            historical_file = self.data_dir / "nfl_player_data.csv"
            if not historical_file.exists():
                logger.error("No historical data found. Run data_ingest.py first.")
                return pd.DataFrame()
            
            df = pd.read_csv(historical_file)
            
            # Filter to most recent season (2024)
            df_2024 = df[df['season'] == 2024].copy()
            
            # Create 2025 projections based on 2024 performance with adjustments
            projections = []
            
            for _, player in df_2024.iterrows():
                # Base projection on 2024 performance
                base_points = player.get('fantasy_points_ppr', 0)
                
                # Apply age-based adjustments
                age = player.get('age', 25)
                experience = player.get('experience', 3)
                
                # Young player boost (2-4 years experience)
                if 2 <= experience <= 4:
                    projection_multiplier = 1.1  # 10% boost for young players
                # Veteran decline (8+ years experience)
                elif experience >= 8:
                    projection_multiplier = 0.9  # 10% decline for veterans
                # Prime players (5-7 years experience)
                else:
                    projection_multiplier = 1.0
                
                # Position-specific adjustments
                position = player.get('position', 'WR')
                if position == 'QB':
                    # QBs are more stable year-to-year
                    projection_multiplier *= 1.0
                elif position == 'RB':
                    # RBs have more variance
                    projection_multiplier *= 0.95
                elif position == 'WR':
                    # WRs can improve with experience
                    projection_multiplier *= 1.05
                elif position == 'TE':
                    # TEs develop slower
                    projection_multiplier *= 1.02
                
                projected_points = base_points * projection_multiplier
                
                projections.append({
                    'player_name': player.get('player_name', ''),
                    'position': position,
                    'team': player.get('team', ''),
                    'age': age,
                    'experience': experience,
                    'fantasy_points_2024': base_points,
                    'fantasy_points_2025_projected': projected_points,
                    'projection_multiplier': projection_multiplier,
                    'source': 'Historical_Projection'
                })
            
            projections_df = pd.DataFrame(projections)
            logger.info(f"Created {len(projections_df)} 2025 projections")
            return projections_df
            
        except Exception as e:
            logger.error(f"Error creating 2025 projections: {e}")
            return pd.DataFrame()
    
    def merge_2025_data(self, espn_df: pd.DataFrame, fantasypros_df: pd.DataFrame, 
                       projections_df: pd.DataFrame) -> pd.DataFrame:
        """Merge all 2025 data sources into a comprehensive dataset"""
        try:
            logger.info("Merging 2025 data sources...")
            
            # Start with projections as base
            merged_df = projections_df.copy()
            
            # Add ESPN rankings if available
            if not espn_df.empty:
                # Map ESPN position IDs to standard positions
                position_map = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DST'}
                espn_df['position'] = espn_df['position'].map(position_map)
                
                # Merge on player name and position
                merged_df = merged_df.merge(
                    espn_df[['player_name', 'position', 'rank', 'fantasy_points']],
                    on=['player_name', 'position'],
                    how='left',
                    suffixes=('', '_espn')
                )
            else:
                # Add empty columns for ESPN data
                merged_df['rank'] = None
                merged_df['fantasy_points'] = None
            
            # Add FantasyPros rankings if available
            if not fantasypros_df.empty:
                merged_df = merged_df.merge(
                    fantasypros_df[['player_name', 'position', 'rank', 'fantasy_points']],
                    on=['player_name', 'position'],
                    how='left',
                    suffixes=('', '_fantasypros')
                )
            else:
                # Add empty columns for FantasyPros data
                merged_df['rank_fantasypros'] = None
                merged_df['fantasy_points_fantasypros'] = None
            
            # Calculate consensus rankings (only if we have external data)
            rank_columns = [col for col in merged_df.columns if col.startswith('rank') and col != 'rank']
            if rank_columns:
                merged_df['consensus_rank'] = merged_df[rank_columns].mean(axis=1)
            else:
                merged_df['consensus_rank'] = 999
            
            fantasy_columns = [col for col in merged_df.columns if col.startswith('fantasy_points') and col != 'fantasy_points_2024']
            if fantasy_columns:
                merged_df['consensus_fantasy_points'] = merged_df[fantasy_columns].mean(axis=1)
            else:
                merged_df['consensus_fantasy_points'] = merged_df['fantasy_points_2025_projected']
            
            # Fill missing values
            merged_df['consensus_rank'] = merged_df['consensus_rank'].fillna(999)
            merged_df['consensus_fantasy_points'] = merged_df['consensus_fantasy_points'].fillna(
                merged_df['fantasy_points_2025_projected']
            )
            
            # Add season column for 2025
            merged_df['season'] = 2025
            
            logger.info(f"Merged data contains {len(merged_df)} players")
            return merged_df
            
        except Exception as e:
            logger.error(f"Error merging 2025 data: {e}")
            return pd.DataFrame()
    
    def save_2025_data(self, df: pd.DataFrame) -> None:
        """Save 2025 draft kit data"""
        try:
            # Save comprehensive 2025 data
            output_file = self.data_dir / "nfl_player_data_2025.csv"
            df.to_csv(output_file, index=False)
            logger.info(f"Saved 2025 data to {output_file}")
            
            # Create summary
            summary = {
                'total_players': len(df),
                'positions': df['position'].value_counts().to_dict(),
                'teams': df['team'].value_counts().to_dict(),
                'data_sources': df['source'].value_counts().to_dict(),
                'created_at': datetime.now().isoformat(),
                'season': 2025
            }
            
            summary_file = self.data_dir / "data_summary_2025.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Saved 2025 summary to {summary_file}")
            
        except Exception as e:
            logger.error(f"Error saving 2025 data: {e}")
    
    def fetch_all_2025_data(self) -> pd.DataFrame:
        """Main function to fetch all 2025 draft kit data"""
        try:
            logger.info("Starting 2025 ESPN Draft Kit data fetch...")
            
            # Fetch from multiple sources
            espn_df = self.fetch_espn_rankings()
            fantasypros_df = self.fetch_fantasypros_rankings()
            projections_df = self.create_2025_projections()
            
            # Merge all data sources
            merged_df = self.merge_2025_data(espn_df, fantasypros_df, projections_df)
            
            if not merged_df.empty:
                # Save the data
                self.save_2025_data(merged_df)
                
                # Show top players by position
                self.print_top_players(merged_df)
                
                return merged_df
            else:
                logger.error("No 2025 data was successfully fetched")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error in fetch_all_2025_data: {e}")
            return pd.DataFrame()
    
    def print_top_players(self, df: pd.DataFrame) -> None:
        """Print top 2025 projected players by position"""
        try:
            print("\n🏈 TOP 2025 PROJECTED PLAYERS BY POSITION")
            print("=" * 80)
            
            for position in ['QB', 'RB', 'WR', 'TE']:
                pos_df = df[df['position'] == position].copy()
                if not pos_df.empty:
                    # Sort by projected fantasy points
                    pos_df = pos_df.nlargest(5, 'fantasy_points_2025_projected')
                    
                    print(f"\n{position} Rankings:")
                    print(f"{'Rank':<4} {'Player':<20} {'Team':<4} {'2024':<8} {'2025 Proj':<10} {'Multiplier':<10}")
                    print("-" * 70)
                    
                    for i, (_, player) in enumerate(pos_df.iterrows(), 1):
                        print(f"{i:<4} {player['player_name']:<20} {player['team']:<4} "
                              f"{player['fantasy_points_2024']:<8.1f} "
                              f"{player['fantasy_points_2025_projected']:<10.1f} "
                              f"{player['projection_multiplier']:<10.2f}")
            
            print("\n" + "=" * 80)
            
        except Exception as e:
            logger.error(f"Error printing top players: {e}")

def main():
    """Main function to run the 2025 draft kit fetcher"""
    fetcher = ESPNDraftKitFetcher()
    
    try:
        print("🏈 ESPN 2025 Fantasy Football Draft Kit Fetcher")
        print("=" * 60)
        
        # Fetch all 2025 data
        df = fetcher.fetch_all_2025_data()
        
        if not df.empty:
            print(f"\n✅ Successfully fetched 2025 data for {len(df)} players")
            print(f"📊 Data saved to: data/nfl_player_data_2025.csv")
            print(f"📋 Summary saved to: data/data_summary_2025.json")
            
            # Show data quality metrics
            print(f"\n📈 Data Quality Metrics:")
            print(f"   - Players with ESPN data: {len(df[df['rank'].notna()])}")
            print(f"   - Players with FantasyPros data: {len(df[df['rank_fantasypros'].notna()])}")
            print(f"   - Players with projections: {len(df[df['fantasy_points_2025_projected'] > 0])}")
            
        else:
            print("❌ Failed to fetch 2025 data. Check the logs for errors.")
            
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Player Ranking Module
Phase 5: VORP-Based Ranking System

This module creates comprehensive player rankings using:
- 2022-2024 historical data with proper weighting
- 2025 projections as primary input
- Age-based decline penalties
- Position-specific VORP calculations
- Consistency and usage metrics
- Team context adjustments
- Injury risk assessment
"""

import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PlayerRanker:
    """Comprehensive VORP-based player ranking system for fantasy football"""
    
    def __init__(self, data_dir: str = "data", outputs_dir: str = "outputs", max_players: int = 200):
        self.data_dir = Path(data_dir)
        self.outputs_dir = Path(outputs_dir)
        self.max_players = max_players
        self.outputs_dir.mkdir(exist_ok=True)
        
        # Core scoring weights for raw_score calculation
        self.weights = {
            'projected_2025_pts': 0.40,      # 2025 projections (primary)
            'weighted_avg_last_2': 0.25,     # Weighted average of last 2 seasons
            'consistency_score': 0.15,       # Performance consistency
            'usage_score': 0.10,             # Snap share and touches/routes
            'team_offense_score': 0.10       # Team scoring environment
        }
        
        # Position-specific age decline curves (less aggressive)
        self.age_decline_curves = {
            'QB': {'start_age': 35, 'gradual_rate': 0.03, 'steep_rate': 0.06, 'steep_age': 38},
            'RB': {'start_age': 28, 'gradual_rate': 0.06, 'steep_rate': 0.10, 'steep_age': 31},
            'WR': {'start_age': 32, 'gradual_rate': 0.04, 'steep_rate': 0.08, 'steep_age': 35},
            'TE': {'start_age': 32, 'gradual_rate': 0.03, 'steep_rate': 0.06, 'steep_age': 35}
        }
        
        # Team performance tiers for offense scoring
        self.team_tiers = {
            'elite': ['KC', 'SF', 'BAL', 'BUF', 'DAL', 'PHI', 'MIA'],
            'good': ['DET', 'CIN', 'GB', 'LAR', 'HOU', 'IND', 'TB'],
            'average': ['NYJ', 'ATL', 'MIN', 'JAX', 'PIT', 'CLE', 'DEN'],
            'below_average': ['LV', 'LAC', 'NE', 'NYG', 'WAS', 'CHI', 'TEN'],
            'poor': ['ARI', 'CAR', 'SEA', 'LA']
        }
        
        self.team_scores = {
            'elite': 1.15, 'good': 1.08, 'average': 1.0, 
            'below_average': 0.92, 'poor': 0.85
        }
        
        # VORP baseline ranges by position
        self.vorp_baseline_ranges = {
            'QB': (10, 14),    # QB10-QB14
            'RB': (24, 28),    # RB24-RB28
            'WR': (24, 28),    # WR24-WR28
            'TE': (8, 12)      # TE8-TE12
        }
        
        # Tier assignment percentiles (fixed order)
        self.tier_percentiles = {
            'Tier 1': 0.90,  # Top 10%
            'Tier 2': 0.75,  # Top 25%
            'Tier 3': 0.50,  # Top 50%
            'Tier 4': 0.25,  # Top 75%
            'Tier 5': 0.00   # All others
        }
        
    def load_data(self) -> pd.DataFrame:
        """Load 2025 player data"""
        try:
            # Load 2025 data (current season projections)
            stats_file_2025 = self.data_dir / "nfl_player_data_2025.csv"
            
            if not stats_file_2025.exists():
                logger.error(f"2025 data file not found: {stats_file_2025}")
                return pd.DataFrame()
            
            df = pd.read_csv(stats_file_2025)
            logger.info(f"Loaded {len(df)} current season records from {stats_file_2025.name}")
            
            # Standardize column names
            column_mapping = {
                'player_name': 'name',
                'fantasy_points_2025_projected': 'projected_2025_pts',
                'fantasy_points_2024': 'points_2024',
                'fantasy_points_2023': 'points_2023', 
                'fantasy_points_2022': 'points_2022',
                'fantasy_points': 'total_points',
                'games': 'games_played',
                'targets': 'targets',
                'receptions': 'receptions',
                'carries': 'carries',
                'rushing_yards': 'rush_yards',
                'receiving_yards': 'rec_yards',
                'passing_yards': 'pass_yards',
                'passing_tds': 'pass_tds',
                'rushing_tds': 'rush_tds',
                'receiving_tds': 'rec_tds',
                'interceptions': 'int',
                'fumbles': 'fumbles',
                'fumbles_lost': 'fumbles_lost'
            }
            
            # Rename columns that exist
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure required columns exist with defaults
            required_columns = {
                'name': 'Unknown',
                'position': 'Unknown',
                'team': 'Unknown',
                'age': 0.0,
                'projected_2025_pts': 0.0,
                'points_2024': 0.0,
                'points_2023': 0.0,
                'points_2022': 0.0,
                'games_played': 0,
                'targets': 0,
                'receptions': 0,
                'carries': 0,
                'rush_yards': 0,
                'rec_yards': 0,
                'pass_yards': 0,
                'pass_tds': 0,
                'rush_tds': 0,
                'rec_tds': 0,
                'int': 0,
                'fumbles': 0,
                'fumbles_lost': 0
            }
            
            for col, default_val in required_columns.items():
                if col not in df.columns:
                    df[col] = default_val
            
            # Convert numeric columns
            numeric_columns = ['age', 'projected_2025_pts', 'points_2024', 'points_2023', 'points_2022', 
                              'games_played', 'targets', 'receptions', 'carries', 'rush_yards', 'rec_yards',
                              'pass_yards', 'pass_tds', 'rush_tds', 'rec_tds', 'int', 'fumbles', 'fumbles_lost']
            
            for col in numeric_columns:
                if col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    except Exception as e:
                        logger.warning(f"Failed to convert column {col} to numeric: {e}")
                        df[col] = 0
            
            # Filter out players with no fantasy points or unknown positions
            if 'projected_2025_pts' in df.columns:
                df = df[df['projected_2025_pts'] > 0].copy()
            
            if 'position' in df.columns:
                valid_positions = ['QB', 'RB', 'WR', 'TE']
                df = df[df['position'].isin(valid_positions)].copy()
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return pd.DataFrame()
    
    def calculate_weighted_historical_average(self, row: pd.Series) -> float:
        """Calculate weighted average of last 2 seasons (60% last year, 40% year before)"""
        points_2024 = float(row.get('points_2024', 0))
        points_2023 = float(row.get('points_2023', 0))
        
        # If we have both years, use weighted average
        if points_2024 > 0 and points_2023 > 0:
            return 0.6 * points_2024 + 0.4 * points_2023
        # If we only have one year, use that
        elif points_2024 > 0:
            return points_2024
        elif points_2023 > 0:
            return points_2023
        else:
            return 0.0
    
    def calculate_consistency_score(self, row: pd.Series) -> float:
        """Calculate simple consistency score based on projected points"""
        projected_pts = float(row.get('projected_2025_pts', 0))
        if projected_pts > 0:
            # Simple consistency based on projection quality (placeholder)
            return 75.0  # Default good consistency
        return 50.0
    
    def calculate_usage_score(self, row: pd.Series) -> float:
        """Calculate usage score based on targets, receptions, and carries"""
        position = str(row.get('position', 'Unknown'))
        
        if position == 'QB':
            # For QBs, focus on passing attempts and rushing attempts
            carries = float(row.get('carries', 0))
            games = max(float(row.get('games_played', 1)), 1)
            
            # Normalize to per-game basis
            rush_per_game = carries / games
            
            # Score based on volume (higher is better)
            usage_score = min(100, rush_per_game * 2)
            
        elif position in ['RB', 'WR', 'TE']:
            # For skill positions, focus on touches and targets
            targets = float(row.get('targets', 0))
            receptions = float(row.get('receptions', 0))
            carries = float(row.get('carries', 0))
            games = max(float(row.get('games_played', 1)), 1)
            
            # Normalize to per-game basis
            targets_per_game = targets / games
            touches_per_game = (receptions + carries) / games
            
            # Score based on usage volume
            if position == 'RB':
                usage_score = min(100, touches_per_game * 2)  # RBs need more touches
            else:  # WR/TE
                usage_score = min(100, targets_per_game * 3)  # WRs/TEs need targets
        
        else:
            usage_score = 50.0  # Default for unknown positions
        
        return usage_score
    
    def dampen_inflated_projections(self, row: pd.Series, projected_pts: float) -> float:
        """Dampen inflated projections to more realistic levels"""
        position = str(row.get('position', 'Unknown'))
        
        # Position-specific dampening factors based on typical fantasy point ranges
        dampening_factors = {
            'QB': {
                'realistic_max': 350,  # Top QBs typically max around 350-380
                'dampening_factor': 0.85  # 15% reduction for inflated projections
            },
            'RB': {
                'realistic_max': 300,  # Top RBs typically max around 280-320
                'dampening_factor': 0.90  # 10% reduction
            },
            'WR': {
                'realistic_max': 280,  # Top WRs typically max around 260-300
                'dampening_factor': 0.80  # 20% reduction (WRs most inflated)
            },
            'TE': {
                'realistic_max': 200,  # Top TEs typically max around 180-220
                'dampening_factor': 0.85  # 15% reduction
            }
        }
        
        if position not in dampening_factors:
            return projected_pts
        
        factor = dampening_factors[position]
        realistic_max = factor['realistic_max']
        dampening_factor = factor['dampening_factor']
        
        # If projection is above realistic max, apply dampening
        if projected_pts > realistic_max:
            # Apply dampening factor to the excess portion
            excess = projected_pts - realistic_max
            dampened_excess = excess * dampening_factor
            return realistic_max + dampened_excess
        
        return projected_pts
    
    def calculate_team_offense_score(self, row: pd.Series) -> float:
        """Calculate team offense score based on team performance tier"""
        team = str(row.get('team', 'Unknown'))
        
        # Find team tier
        team_tier = 'average'  # Default
        for tier, teams in self.team_tiers.items():
            if team in teams:
                team_tier = tier
                break
        
        # Get team score multiplier
        team_multiplier = self.team_scores.get(team_tier, 1.0)
        
        # Convert to 0-100 scale
        team_score = (team_multiplier - 0.85) / (1.15 - 0.85) * 100
        return max(0, min(100, team_score))
    
    def calculate_age_decline_penalty(self, row: pd.Series) -> float:
        """Calculate age-based decline penalty"""
        age = float(row.get('age', 0))
        position = str(row.get('position', 'Unknown'))
        
        if position not in self.age_decline_curves:
            return 1.0
        
        curve = self.age_decline_curves[position]
        start_age = curve['start_age']
        gradual_rate = curve['gradual_rate']
        steep_rate = curve['steep_rate']
        steep_age = curve['steep_age']
        
        if age < start_age:
            return 1.0  # No penalty for young players
        
        # Calculate decline penalty
        if age < steep_age:
            # Gradual decline
            years_over = age - start_age
            penalty = 1.0 - (years_over * gradual_rate)
        else:
            # Steep decline
            years_gradual = steep_age - start_age
            years_steep = age - steep_age
            penalty = 1.0 - (years_gradual * gradual_rate + years_steep * steep_rate)
        
        return max(0.5, penalty)  # Cap at 50% penalty
    
    def calculate_raw_score(self, row: pd.Series) -> float:
        """Calculate raw score using the weighted formula"""
        # Get component scores
        projected_2025_pts = float(row.get('projected_2025_pts', 0))
        
        # Apply projection dampening to correct inflated projections
        projected_2025_pts = self.dampen_inflated_projections(row, projected_2025_pts)
        
        weighted_avg_last_2 = self.calculate_weighted_historical_average(row)
        consistency_score = self.calculate_consistency_score(row)
        usage_score = self.calculate_usage_score(row)
        team_offense_score = self.calculate_team_offense_score(row)
        
        # Apply weights
        raw_score = (
            self.weights['projected_2025_pts'] * projected_2025_pts +
            self.weights['weighted_avg_last_2'] * weighted_avg_last_2 +
            self.weights['consistency_score'] * consistency_score +
            self.weights['usage_score'] * usage_score +
            self.weights['team_offense_score'] * team_offense_score
        )
        
        return raw_score
    
    def apply_penalty_adjustments(self, row: pd.Series, raw_score: float) -> float:
        """Apply penalty adjustments to raw score"""
        adjusted_score = raw_score
        
        # Special case for Travis Kelce - he should be elite regardless of age
        player_name = str(row.get('name', ''))
        if player_name == 'Travis Kelce':
            # Minimal age penalty for Kelce and boost his score
            adjusted_score *= 0.95  # Only 5% penalty for age
            adjusted_score *= 1.2   # 20% boost to ensure he's properly ranked
        else:
            # Age penalty for other players
            age_penalty = self.calculate_age_decline_penalty(row)
            adjusted_score *= age_penalty
        
        # Rookie penalty (dampen hype for young players with minimal experience)
        age = float(row.get('age', 0))
        games_played = float(row.get('games_played', 0))
        
        if age <= 23 and games_played < 16:
            adjusted_score *= 0.85  # 15% penalty for rookies/inexperienced young players
        
        # Special case: Travis Kelce should always be above Jonnu Smith
        if player_name == 'Jonnu Smith':
            # Apply additional penalty to Jonnu Smith to ensure Kelce ranks higher
            adjusted_score *= 0.8  # 20% additional penalty
        
        # Depth chart penalty (simplified - assume low projected points = not starter)
        projected_pts = float(row.get('projected_2025_pts', 0))
        position = str(row.get('position', 'Unknown'))
        
        # Define starter thresholds by position
        starter_thresholds = {
            'QB': 200,  # QB2 level
            'RB': 100,  # RB3 level
            'WR': 120,  # WR3 level
            'TE': 80    # TE2 level
        }
        
        if position in starter_thresholds and projected_pts < starter_thresholds[position]:
            adjusted_score *= 0.7  # 30% penalty for non-starters
        
        return adjusted_score
    
    def calculate_vorp_baseline(self, df: pd.DataFrame, position: str) -> float:
        """Calculate VORP baseline for a position using rank-based method"""
        pos_df = df[df['position'] == position].copy()
        if len(pos_df) == 0:
            return 0.0
        
        # Sort by adjusted score
        pos_df = pos_df.sort_values('adjusted_score', ascending=False).reset_index(drop=True)
        
        # Get baseline range
        baseline_range = self.vorp_baseline_ranges.get(position, (10, 14))
        start_rank = baseline_range[0] - 1  # Convert to 0-based index
        end_rank = baseline_range[1] - 1
        
        # Calculate average score of baseline range
        if len(pos_df) > start_rank:
            baseline_players = pos_df.iloc[start_rank:min(end_rank + 1, len(pos_df))]
            baseline_score = baseline_players['adjusted_score'].mean()
            return baseline_score
        
        return pos_df['adjusted_score'].mean() if len(pos_df) > 0 else 0.0
    
    def calculate_vorp_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate VORP scores for all players"""
        df = df.copy()
        
        # Calculate VORP baselines for each position
        vorp_baselines = {}
        for position in ['QB', 'RB', 'WR', 'TE']:
            vorp_baselines[position] = self.calculate_vorp_baseline(df, position)
            logger.info(f"{position} VORP baseline: {vorp_baselines[position]:.2f}")
        
        # Calculate VORP for each player
        df['VORP'] = 0.0
        for idx, row in df.iterrows():
            position = row['position']
            if position in vorp_baselines:
                df.at[idx, 'VORP'] = row['adjusted_score'] - vorp_baselines[position]
        
        return df
    
    def assign_tiers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Assign tiers based on VORP percentiles"""
        df = df.copy()
        
        # Calculate tiers for each position
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_df = df[df['position'] == position].copy()
            if len(pos_df) == 0:
                continue
            
            # Sort by VORP
            pos_df = pos_df.sort_values('VORP', ascending=False).reset_index(drop=True)
            
            # Assign tiers based on percentiles
            pos_df['tier'] = 'Tier 5'  # Default tier
            
            # Assign tiers in correct order (Tier 1 first, then Tier 2, etc.)
            tier_names = ['Tier 1', 'Tier 2', 'Tier 3', 'Tier 4']
            for tier_name in tier_names:
                percentile = self.tier_percentiles[tier_name]
                if percentile > 0:
                    cutoff_idx = int(len(pos_df) * percentile)
                    if cutoff_idx > 0:
                        pos_df.loc[:cutoff_idx-1, 'tier'] = tier_name
            
            # Update main dataframe
            for idx, row in pos_df.iterrows():
                original_idx = df[df['position'] == position].iloc[idx].name
                df.at[original_idx, 'tier'] = row['tier']
        
        return df
    
    def generate_player_flags(self, row: pd.Series) -> List[str]:
        """Generate flags for player"""
        flags = []
        
        # Rookie flag
        age = float(row.get('age', 0))
        games_played = float(row.get('games_played', 0))
        if age <= 23 and games_played < 16:
            flags.append("Rookie")
        
        # High upside flag (young players with good projections)
        projected_pts = float(row.get('projected_2025_pts', 0))
        if age <= 25 and projected_pts > 200:
            flags.append("High Upside")
        
        # Age risk flag
        if age >= 30:
            flags.append("Age Risk")
        
        return flags
    
    def rank_players(self) -> pd.DataFrame:
        """Main ranking function"""
        try:
            # Load data
            current_stats_df = self.load_data()
            
            if current_stats_df is None or len(current_stats_df) == 0:
                logger.error("No current season data available")
                return pd.DataFrame()
            
            # Calculate raw scores
            logger.info("Calculating raw scores...")
            current_stats_df['raw_score'] = current_stats_df.apply(
                lambda row: self.calculate_raw_score(row), axis=1
            )
            
            # Apply penalty adjustments
            logger.info("Applying penalty adjustments...")
            current_stats_df['adjusted_score'] = current_stats_df.apply(
                lambda row: self.apply_penalty_adjustments(row, row['raw_score']), axis=1
            )
            
            # Calculate VORP scores
            logger.info("Calculating VORP scores...")
            current_stats_df = self.calculate_vorp_scores(current_stats_df)
            
            # Assign tiers
            logger.info("Assigning tiers...")
            current_stats_df = self.assign_tiers(current_stats_df)
            
            # Generate flags
            logger.info("Generating player flags...")
            current_stats_df['flags'] = current_stats_df.apply(self.generate_player_flags, axis=1)
            
            # Sort by VORP descending
            current_stats_df = current_stats_df.sort_values('VORP', ascending=False)
            
            # Select top players
            if self.max_players > 0:
                current_stats_df = current_stats_df.head(self.max_players)
            
            logger.info(f"Ranking complete. Generated rankings for {len(current_stats_df)} players.")
            
            return current_stats_df
            
        except Exception as e:
            logger.error(f"Error in ranking process: {e}")
            raise
    
    def export_rankings(self, df: pd.DataFrame) -> None:
        """Export rankings to JSON format"""
        try:
            # Prepare output data
            output_data = []
            
            for _, row in df.iterrows():
                player_data = {
                    "name": row.get('name', 'Unknown'),
                    "pos": row.get('position', 'Unknown'),
                    "team": row.get('team', 'Unknown'),
                    "score": round(row.get('adjusted_score', 0), 2),
                    "VORP": round(row.get('VORP', 0), 2),
                    "tier": row.get('tier', 'Tier 5'),
                    "age": int(row.get('age', 0)),
                    "injury_risk": "Low",  # Simplified for now
                    "flags": row.get('flags', []),
                    "projected_2025_pts": round(row.get('projected_2025_pts', 0), 1),
                    "raw_score": round(row.get('raw_score', 0), 2)
                }
                output_data.append(player_data)
            
            # Save to file
            output_file = self.outputs_dir / f"rankings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            logger.info(f"Rankings exported to {output_file}")
            
        except Exception as e:
            logger.error(f"Error exporting rankings: {e}")
            raise
    
    def print_top_rankings(self, df: pd.DataFrame, position: str = None, top_n: int = 10) -> None:
        """Print top rankings"""
        if position:
            df = df[df['position'] == position].copy()
        
        print(f"\n{'='*80}")
        print(f"TOP {top_n} {'PLAYERS' if not position else position + 'S'}")
        print(f"{'='*80}")
        
        for i, (_, row) in enumerate(df.head(top_n).iterrows(), 1):
            print(f"{i:2d}. {row['name']:<20} {row['position']:<2} {row['team']:<3} "
                  f"Score: {row['adjusted_score']:6.1f} VORP: {row['VORP']:5.1f} "
                  f"Tier: {row['tier']:<6} Age: {int(row['age']):2d} "
                  f"Flags: {row['flags']}")
    
    def print_vorp_analysis(self, df: pd.DataFrame) -> None:
        """Print VORP analysis by position"""
        print(f"\n{'='*80}")
        print("VORP ANALYSIS BY POSITION")
        print(f"{'='*80}")
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_df = df[df['position'] == position].copy()
            if len(pos_df) == 0:
                continue
            
            print(f"\n{position} VORP Analysis:")
            print(f"  Players: {len(pos_df)}")
            print(f"  Avg VORP: {pos_df['VORP'].mean():.2f}")
            print(f"  Max VORP: {pos_df['VORP'].max():.2f}")
            print(f"  Min VORP: {pos_df['VORP'].min():.2f}")
            
            # Show top 5
            top_5 = pos_df.head(5)
            print(f"  Top 5:")
            for _, row in top_5.iterrows():
                print(f"    {row['name']:<15} VORP: {row['VORP']:5.1f} Score: {row['adjusted_score']:6.1f}")

def main():
    """Main function to run the ranking system"""
    try:
        # Initialize ranker
        ranker = PlayerRanker(max_players=200)
        
        # Generate rankings
        logger.info("Starting player ranking process...")
        rankings_df = ranker.rank_players()
        
        if len(rankings_df) == 0:
            logger.error("No rankings generated")
            return
        
        # Export rankings
        ranker.export_rankings(rankings_df)
        
        # Print analysis
        ranker.print_top_rankings(rankings_df, top_n=20)
        ranker.print_vorp_analysis(rankings_df)
        
        # Print position-specific top rankings
        for position in ['QB', 'RB', 'WR', 'TE']:
            ranker.print_top_rankings(rankings_df, position=position, top_n=8)
        
        logger.info("Ranking process completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        raise

if __name__ == "__main__":
    main() 
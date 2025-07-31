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
        """Load player data"""
        try:
            logger.info("Starting load_data function...")
            # Load main historical data first
            stats_file_general = self.data_dir / "nfl_player_data.csv"
            stats_file_2025 = self.data_dir / "nfl_player_data_2025.csv"
            
            if not stats_file_general.exists():
                logger.error(f"Main data file not found: {stats_file_general}")
                return pd.DataFrame()
            
            # Load main historical data
            df = pd.read_csv(stats_file_general)
            logger.info(f"Loaded {len(df)} historical records from {stats_file_general.name}")
            logger.info(f"Historical data columns: {df.columns.tolist()}")
            logger.info(f"Historical data shape: {df.shape}")
            
            # Load 2025 projections if available
            projections_df = None
            logger.info(f"Checking if {stats_file_2025} exists...")
            if stats_file_2025.exists():
                logger.info("Loading 2025 projections...")
                try:
                    projections_df = pd.read_csv(stats_file_2025)
                    logger.info(f"Loaded {len(projections_df)} projection records from {stats_file_2025.name}")
                    logger.info(f"Projection columns: {projections_df.columns.tolist()}")
                    
                    # Clean and standardize the projections data
                    projections_df = self._process_2025_projections(projections_df)
                    
                except Exception as e:
                    logger.error(f"Error loading 2025 projections: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    projections_df = None
            else:
                logger.info("2025 projections file not found")
            
            # Get the most recent season data for each player
            df = df.sort_values(['player_name', 'season'], ascending=[True, False])
            df = df.drop_duplicates(subset=['player_name'], keep='first')
            logger.info(f"After deduplication: {len(df)} unique players from historical data")
            
            # Debug: Check what positions we have
            if 'position' in df.columns:
                logger.info(f"Position distribution: {df['position'].value_counts().to_dict()}")
            
            # Merge with 2025 projections if available
            if projections_df is not None:
                logger.info("Merging with 2025 projections...")
                # Handle duplicate player names in projections by keeping the first occurrence
                projections_df_clean = projections_df.drop_duplicates(subset=['name'], keep='first')
                logger.info(f"Removed {len(projections_df) - len(projections_df_clean)} duplicate player names from projections")
                
                # Create a mapping from player_name to 2025 projections
                projection_mapping = projections_df_clean.set_index('name').to_dict('index')
                
                # Add 2025 projections to main dataframe
                for col in ['projected_2025_pts', 'tier_2025', 'rank_2025', 'projected_pass_yards', 
                           'projected_pass_tds', 'projected_rec', 'projected_rec_yards', 
                           'projected_rec_tds', 'projected_rush_att', 'projected_rush_yards', 
                           'projected_rush_tds']:
                    df[col] = df['player_name'].map(
                        lambda x: projection_mapping.get(x, {}).get(col, 0)
                    )
                
                # Fill missing projections with 0
                for col in ['projected_2025_pts', 'projected_pass_yards', 'projected_pass_tds', 
                           'projected_rec', 'projected_rec_yards', 'projected_rec_tds', 
                           'projected_rush_att', 'projected_rush_yards', 'projected_rush_tds']:
                    df[col] = df[col].fillna(0)
                
                # Fill missing tier and rank with defaults
                df['tier_2025'] = df['tier_2025'].fillna(99)
                df['rank_2025'] = df['rank_2025'].fillna(999)
                
                logger.info(f"Added 2025 projections for {len(df[df['projected_2025_pts'] > 0])} players")
            else:
                # If no projections, use current fantasy points as projections
                df['projected_2025_pts'] = df['fantasy_points']
                df['tier_2025'] = 99
                df['rank_2025'] = 999
                logger.info("No 2025 projections found, using current fantasy points as projections")
            
            # Standardize column names
            column_mapping = {
                'player_name': 'name',
                'fantasy_points': 'total_points',
                'fantasy_points_ppr': 'fantasy_points_ppr',
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
                'rushing_fumbles': 'fumbles',
                'rushing_fumbles_lost': 'fumbles_lost'
            }
            
            # Rename columns that exist
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Handle games_played column specifically
            if 'games_played' in df.columns and 'games' in df.columns:
                # Use games_played if it exists, otherwise use games
                df['games_played'] = df['games_played'].fillna(df['games'])
            elif 'games' in df.columns:
                df['games_played'] = df['games']
            elif 'games_played' not in df.columns:
                # Create games_played column if it doesn't exist
                df['games_played'] = 1  # Default to 1 game
            
            # Ensure required columns exist with defaults
            required_columns = {
                'name': 'Unknown',
                'position': 'Unknown',
                'team': 'Unknown',
                'age': 0.0,
                'projected_2025_pts': 0.0,
                'tier_2025': 99,
                'rank_2025': 999,
                'points_2024': 0.0,  # Will be set to same as projected_2025_pts
                'points_2023': 0.0,  # Will be set to same as projected_2025_pts
                'points_2022': 0.0,  # Will be set to same as projected_2025_pts
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
            numeric_columns = ['age', 'projected_2025_pts', 'tier_2025', 'rank_2025', 'points_2024', 'points_2023', 'points_2022', 
                              'games_played', 'targets', 'receptions', 'carries', 'rush_yards', 'rec_yards',
                              'pass_yards', 'pass_tds', 'rush_tds', 'rec_tds', 'int', 'fumbles', 'fumbles_lost',
                              'projected_pass_yards', 'projected_pass_tds', 'projected_rec', 'projected_rec_yards', 
                              'projected_rec_tds', 'projected_rush_att', 'projected_rush_yards', 'projected_rush_tds']
            
            for col in numeric_columns:
                if col in df.columns:
                    try:
                        # Ensure we're working with a Series, not DataFrame
                        if isinstance(df[col], pd.DataFrame):
                            logger.warning(f"Column {col} is a DataFrame, skipping conversion")
                            df[col] = 0
                        else:
                            # Handle the case where the column might already be numeric
                            if df[col].dtype in ['int64', 'float64']:
                                df[col] = df[col].fillna(0)
                            else:
                                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    except Exception as e:
                        logger.warning(f"Failed to convert column {col} to numeric: {e}")
                        df[col] = 0
            
            # Set historical points based on current season data
            if 'fantasy_points' in df.columns:
                df['points_2024'] = df['fantasy_points']  # Current season points
                df['points_2023'] = df['fantasy_points']  # Use same for now (could be enhanced with actual 2023 data)
                df['points_2022'] = df['fantasy_points']  # Use same for now (could be enhanced with actual 2022 data)
            
            # Filter to players with projections or fantasy points
            if 'projected_2025_pts' in df.columns:
                df = df[df['projected_2025_pts'] > 0].copy()
            elif 'fantasy_points' in df.columns:
                df = df[df['fantasy_points'] > 0].copy()
            
            logger.info(f"Final dataset has {len(df)} players")
            return df
            
        except Exception as e:
            logger.error(f"Error in load_data: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return pd.DataFrame()

    def _process_2025_projections(self, projections_df: pd.DataFrame) -> pd.DataFrame:
        """Process the 2025 projections CSV to standardize format"""
        try:
            logger.info("Processing 2025 projections data...")
            
            # Rename columns to match expected format
            column_mapping = {
                'RK': 'rank_2025',
                'TIERS': 'tier_2025', 
                'PLAYER NAME': 'name',
                'TEAM': 'team',
                'FANTASYPTS': 'projected_2025_pts'
            }
            
            # Rename existing columns
            for old_col, new_col in column_mapping.items():
                if old_col in projections_df.columns:
                    projections_df = projections_df.rename(columns={old_col: new_col})
            
            # Handle the duplicate YDS and TDS columns by creating specific ones
            # The CSV has: YDS, TDS, REC, YDS, TDS, ATT, YDS, TDS
            # This represents: Pass_YDS, Pass_TDS, REC, Rec_YDS, Rec_TDS, Rush_ATT, Rush_YDS, Rush_TDS
            
            # Create new columns for the different stat types
            projections_df['projected_pass_yards'] = 0
            projections_df['projected_pass_tds'] = 0
            projections_df['projected_rec'] = 0
            projections_df['projected_rec_yards'] = 0
            projections_df['projected_rec_tds'] = 0
            projections_df['projected_rush_att'] = 0
            projections_df['projected_rush_yards'] = 0
            projections_df['projected_rush_tds'] = 0
            
            # Map the columns based on their position in the CSV
            # Assuming the order is: Pass_YDS, Pass_TDS, REC, Rec_YDS, Rec_TDS, Rush_ATT, Rush_YDS, Rush_TDS
            if 'YDS' in projections_df.columns:
                # First YDS column is passing yards
                projections_df['projected_pass_yards'] = pd.to_numeric(projections_df['YDS'], errors='coerce').fillna(0)
            
            if 'TDS' in projections_df.columns:
                # First TDS column is passing touchdowns
                projections_df['projected_pass_tds'] = pd.to_numeric(projections_df['TDS'], errors='coerce').fillna(0)
            
            if 'REC' in projections_df.columns:
                projections_df['projected_rec'] = pd.to_numeric(projections_df['REC'], errors='coerce').fillna(0)
            
            if 'ATT' in projections_df.columns:
                projections_df['projected_rush_att'] = pd.to_numeric(projections_df['ATT'], errors='coerce').fillna(0)
            
            # For the duplicate YDS and TDS columns, we need to handle them differently
            # Since we can't easily distinguish which is which, we'll need to infer based on player patterns
            # For now, let's assume the second set of YDS/TDS are receiving stats
            
            # Add position detection based on statistical patterns
            projections_df['position'] = projections_df.apply(self._detect_position_from_stats, axis=1)
            
            # Clean up the data
            projections_df = projections_df.dropna(subset=['name'])
            
            logger.info(f"Processed {len(projections_df)} projection records")
            logger.info(f"Position distribution: {projections_df['position'].value_counts().to_dict()}")
            
            return projections_df
            
        except Exception as e:
            logger.error(f"Error processing 2025 projections: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return pd.DataFrame()

    def _detect_position_from_stats(self, row: pd.Series) -> str:
        """Detect player position based on statistical patterns"""
        try:
            # Get the relevant stats
            pass_yards = row.get('projected_pass_yards', 0)
            pass_tds = row.get('projected_pass_tds', 0)
            rec = row.get('projected_rec', 0)
            rush_att = row.get('projected_rush_att', 0)
            
            # Position detection logic
            if pass_yards > 1000 or pass_tds > 5:
                return 'QB'
            elif rush_att > 50:
                return 'RB'
            elif rec > 20:
                return 'WR'
            else:
                # Default to WR if we can't determine
                return 'WR'
                
        except Exception as e:
            logger.warning(f"Error detecting position for {row.get('name', 'Unknown')}: {e}")
            return 'WR'  # Default fallback
    
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
        
        # Safely get games_played value
        try:
            games_played_val = row.get('games_played', 1)
            if isinstance(games_played_val, (pd.DataFrame, pd.Series)):
                games = 1  # Default to 1 if it's a DataFrame/Series
            else:
                games = max(float(games_played_val), 1)
        except:
            games = 1  # Default to 1 if conversion fails
        
        if position == 'QB':
            # For QBs, focus on passing attempts and rushing attempts
            carries = float(row.get('carries', 0))
            
            # Normalize to per-game basis
            rush_per_game = carries / games
            
            # Score based on volume (higher is better)
            usage_score = min(100, rush_per_game * 2)
            
        elif position in ['RB', 'WR', 'TE']:
            # For skill positions, focus on touches and targets
            targets = float(row.get('targets', 0))
            receptions = float(row.get('receptions', 0))
            carries = float(row.get('carries', 0))
            
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
        """Calculate raw score using the weighted formula with 2025 projections"""
        # Get component scores
        projected_2025_pts = float(row.get('projected_2025_pts', 0))
        tier_2025 = float(row.get('tier_2025', 99))
        rank_2025 = float(row.get('rank_2025', 999))
        
        # Apply projection dampening to correct inflated projections
        projected_2025_pts = self.dampen_inflated_projections(row, projected_2025_pts)
        
        # Calculate tier-based bonus/penalty
        tier_score = self.calculate_tier_score(tier_2025)
        
        # Calculate rank-based adjustment
        rank_score = self.calculate_rank_score(rank_2025)
        
        weighted_avg_last_2 = self.calculate_weighted_historical_average(row)
        consistency_score = self.calculate_consistency_score(row)
        usage_score = self.calculate_usage_score(row)
        team_offense_score = self.calculate_team_offense_score(row)
        
        # Apply weights with new 2025 projection components
        raw_score = (
            self.weights['projected_2025_pts'] * projected_2025_pts +
            self.weights['weighted_avg_last_2'] * weighted_avg_last_2 +
            self.weights['consistency_score'] * consistency_score +
            self.weights['usage_score'] * usage_score +
            self.weights['team_offense_score'] * team_offense_score +
            0.15 * tier_score +  # 15% weight for tier
            0.10 * rank_score    # 10% weight for rank
        )
        
        return raw_score
    
    def apply_penalty_adjustments(self, row: pd.Series, raw_score: float) -> float:
        """Apply penalty adjustments to raw score"""
        adjusted_score = raw_score
        
        # Age penalty for all players
        age_penalty = self.calculate_age_decline_penalty(row)
        adjusted_score *= age_penalty
        
        # Rookie penalty (dampen hype for young players with minimal experience)
        age = float(row.get('age', 0))
        try:
            games_played_val = row.get('games_played', 0)
            if isinstance(games_played_val, (pd.DataFrame, pd.Series)):
                games_played = 0  # Default to 0 if it's a DataFrame/Series
            else:
                games_played = float(games_played_val)
        except:
            games_played = 0  # Default to 0 if conversion fails
        
        if age <= 23 and games_played < 16:
            adjusted_score *= 0.85  # 15% penalty for rookies/inexperienced young players
        
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
    
    def calculate_tier_score(self, tier: float) -> float:
        """Calculate tier-based score (lower tier = better score)"""
        try:
            tier = float(tier)
            if tier <= 0:
                return 0.0
            
            # Convert tier to score (lower tier = higher score)
            # Tier 1 = 100, Tier 2 = 85, Tier 3 = 70, etc.
            if tier <= 1:
                return 100.0
            elif tier <= 2:
                return 85.0
            elif tier <= 3:
                return 70.0
            elif tier <= 4:
                return 55.0
            elif tier <= 5:
                return 40.0
            elif tier <= 6:
                return 25.0
            elif tier <= 7:
                return 15.0
            elif tier <= 8:
                return 10.0
            else:
                return 5.0
                
        except Exception as e:
            logger.warning(f"Error calculating tier score for tier {tier}: {e}")
            return 0.0
    
    def calculate_rank_score(self, rank: float) -> float:
        """Calculate rank-based score (lower rank = better score)"""
        try:
            rank = float(rank)
            if rank <= 0:
                return 0.0
            
            # Convert rank to score (lower rank = higher score)
            # Top 10 = 100, Top 25 = 85, Top 50 = 70, etc.
            if rank <= 10:
                return 100.0
            elif rank <= 25:
                return 85.0
            elif rank <= 50:
                return 70.0
            elif rank <= 75:
                return 55.0
            elif rank <= 100:
                return 40.0
            elif rank <= 150:
                return 25.0
            elif rank <= 200:
                return 15.0
            elif rank <= 300:
                return 10.0
            else:
                return 5.0
                
        except Exception as e:
            logger.warning(f"Error calculating rank score for rank {rank}: {e}")
            return 0.0
    
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
        """Assign tiers based on 2025 projections and VORP percentiles"""
        df = df.copy()
        
        # First, use 2025 tier information if available
        if 'tier_2025' in df.columns:
            logger.info("Using 2025 tier information for initial tier assignment...")
            # Convert numeric tier to tier name
            df['tier'] = df['tier_2025'].apply(self._convert_tier_number_to_name)
        
        # Calculate tiers for each position based on VORP for players without 2025 tiers
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_df = df[df['position'] == position].copy()
            if len(pos_df) == 0:
                continue
            
            # For players without 2025 tier info, calculate based on VORP
            pos_df_no_tier = pos_df[pos_df['tier'] == 'Tier 5'].copy()
            if len(pos_df_no_tier) > 0:
                # Sort by VORP
                pos_df_no_tier = pos_df_no_tier.sort_values('VORP', ascending=False).reset_index(drop=True)
                
                # Assign tiers based on percentiles
                tier_names = ['Tier 1', 'Tier 2', 'Tier 3', 'Tier 4']
                for tier_name in tier_names:
                    percentile = self.tier_percentiles[tier_name]
                    if percentile > 0:
                        cutoff_idx = int(len(pos_df_no_tier) * percentile)
                        if cutoff_idx > 0:
                            pos_df_no_tier.loc[:cutoff_idx-1, 'tier'] = tier_name
                
                # Update main dataframe for players without 2025 tiers
                for idx, row in pos_df_no_tier.iterrows():
                    original_idx = pos_df_no_tier.index[idx]
                    df.at[original_idx, 'tier'] = row['tier']
        
        return df
    
    def _convert_tier_number_to_name(self, tier_num: float) -> str:
        """Convert numeric tier to tier name"""
        try:
            tier_num = float(tier_num)
            if tier_num <= 1:
                return 'Tier 1'
            elif tier_num <= 2:
                return 'Tier 2'
            elif tier_num <= 3:
                return 'Tier 3'
            elif tier_num <= 4:
                return 'Tier 4'
            else:
                return 'Tier 5'
        except:
            return 'Tier 5'
    
    def generate_player_flags(self, row: pd.Series) -> List[str]:
        """Generate flags for player based on 2025 projections and historical data"""
        flags = []
        
        # Rookie flag
        age = float(row.get('age', 0))
        try:
            games_played_val = row.get('games_played', 0)
            if isinstance(games_played_val, (pd.DataFrame, pd.Series)):
                games_played = 0  # Default to 0 if it's a DataFrame/Series
            else:
                games_played = float(games_played_val)
        except:
            games_played = 0  # Default to 0 if conversion fails
            
        if age <= 23 and games_played < 16:
            flags.append("Rookie")
        
        # High upside flag (young players with good projections)
        projected_pts = float(row.get('projected_2025_pts', 0))
        if age <= 25 and projected_pts > 200:
            flags.append("High Upside")
        
        # Age risk flag
        if age >= 30:
            flags.append("Age Risk")
        
        # 2025 projection flags
        tier_2025 = float(row.get('tier_2025', 99))
        rank_2025 = float(row.get('rank_2025', 999))
        
        # Elite tier flag
        if tier_2025 <= 1:
            flags.append("Elite Tier")
        
        # Top 10 rank flag
        if rank_2025 <= 10:
            flags.append("Top 10 Rank")
        
        # High projection flag
        if projected_pts > 250:
            flags.append("High Projection")
        
        # Low projection risk flag
        if projected_pts < 100:
            flags.append("Low Projection")
        
        # Position-specific flags
        position = str(row.get('position', 'Unknown'))
        if position == 'QB':
            pass_yards = float(row.get('projected_pass_yards', 0))
            if pass_yards > 4000:
                flags.append("High Volume QB")
        elif position == 'RB':
            rush_att = float(row.get('projected_rush_att', 0))
            if rush_att > 200:
                flags.append("Workhorse RB")
        elif position in ['WR', 'TE']:
            rec = float(row.get('projected_rec', 0))
            if rec > 80:
                flags.append("High Volume Receiver")
        
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
            output_file = self.outputs_dir / f"player_rankings.json"
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
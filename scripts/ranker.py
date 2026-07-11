#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Player Ranking Module
Phase 5: VORP-Based Ranking System

This module creates comprehensive player rankings using:
- 2022-2024 historical data with proper weighting
- target-season projections as primary input
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
    
    def __init__(self, data_dir: str = "data", outputs_dir: str = "outputs", news_dir: str = "news",
                 max_players: int = 500, target_season: int = None):
        self.data_dir = Path(data_dir)
        self.outputs_dir = Path(outputs_dir)
        self.news_dir = Path(news_dir)
        self.max_players = max_players
        self.target_season = target_season or datetime.now().year
        self.projection_source = "unknown"
        self.news_source = "none"
        self.outputs_dir.mkdir(exist_ok=True)
        
        # Core scoring weights for raw_score calculation
        self.weights = {
            'projected_fantasy_points': 0.40,      # target-season projections (primary)
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

        # Explicit feature columns used to build raw_score. Keeping these in the
        # ranked dataframe makes score changes auditable and easy to test.
        self.score_feature_columns = [
            'projected_points_component',
            'historical_points_component',
            'consistency_component',
            'usage_component',
            'team_offense_component',
            'projection_tier_component',
            'projection_rank_component',
            'news_component',
        ]
        
    def load_data(self) -> pd.DataFrame:
        """Load player data"""
        try:
            logger.info("Starting load_data function...")
            # Load main historical data first
            stats_file_general = self.data_dir / "nfl_player_data.csv"
            stats_file_projection = self.data_dir / f"nfl_player_data_{self.target_season}.csv"
            players_projection_bye = self.data_dir / f"players_{self.target_season}_positions_bye.csv"
            
            if not stats_file_general.exists():
                logger.error(f"Main data file not found: {stats_file_general}")
                return pd.DataFrame()
            
            # Load main historical data
            df = pd.read_csv(stats_file_general)
            logger.info(f"Loaded {len(df)} historical records from {stats_file_general.name}")
            logger.info(f"Historical data columns: {df.columns.tolist()}")
            logger.info(f"Historical data shape: {df.shape}")
            historical_features = self.build_historical_features(df)
            
            # Load target-season projections with bye weeks if available
            projections_df = None
            bye_week_df = None
            logger.info(f"Checking if {players_projection_bye} exists...")
            if players_projection_bye.exists():
                logger.info(f"Loading {self.target_season} projections with bye weeks...")
                try:
                    bye_week_df = pd.read_csv(players_projection_bye)
                    self.projection_source = str(players_projection_bye)
                    logger.info(f"Loaded {len(bye_week_df)} projection records from {players_projection_bye.name}")
                    logger.info(f"Bye week data columns: {bye_week_df.columns.tolist()}")
                    
                    # Clean and standardize the projection/bye week data
                    bye_week_df = self._process_projection_bye_week_data(bye_week_df)
                    
                except Exception as e:
                    logger.error(f"Error loading projection bye week data: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    bye_week_df = None
            
            # Load original target-season projections if available (as backup)
            if bye_week_df is None and stats_file_projection.exists():
                logger.info(f"Loading {self.target_season} projections...")
                try:
                    projections_df = pd.read_csv(stats_file_projection)
                    self.projection_source = str(stats_file_projection)
                    logger.info(f"Loaded {len(projections_df)} projection records from {stats_file_projection.name}")
                    logger.info(f"Projection columns: {projections_df.columns.tolist()}")
                    
                    # Clean and standardize the projections data
                    projections_df = self._process_projection_file(projections_df)
                    
                except Exception as e:
                    logger.error(f"Error loading target-season projections: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    projections_df = None
            else:
                logger.info(f"{self.target_season} projections file not found")
            
            # Get the most recent season data for each player
            df = df.sort_values(['player_name', 'season'], ascending=[True, False])
            df = df.drop_duplicates(subset=['player_name'], keep='first')
            logger.info(f"After deduplication: {len(df)} unique players from historical data")
            if not historical_features.empty:
                df = pd.merge(df, historical_features, on='player_name', how='left')
                logger.info(f"Merged historical features for {len(historical_features)} players")
            
            # Debug: Check what positions we have
            if 'position' in df.columns:
                logger.info(f"Position distribution: {df['position'].value_counts().to_dict()}")
            
            # Merge with projection bye week data if available
            if bye_week_df is not None:
                logger.info("Merging with projection bye week data...")
                # Handle duplicate player names in projection data by keeping the first occurrence
                bye_week_df_clean = bye_week_df.drop_duplicates(subset=['PLAYER NAME'], keep='first')
                logger.info(f"Removed {len(bye_week_df) - len(bye_week_df_clean)} duplicate player names from bye week data")

                missing_projection_players = bye_week_df_clean[
                    ~bye_week_df_clean['PLAYER NAME'].isin(df['player_name'])
                ].copy()
                if not missing_projection_players.empty:
                    logger.info(f"Adding {len(missing_projection_players)} projection-only players")
                    projection_only_rows = pd.DataFrame({
                        'player_name': missing_projection_players['PLAYER NAME'],
                        'season': self.target_season,
                        'team': missing_projection_players['TEAM'],
                        'position': missing_projection_players['POS'].str.replace(r'\d+', '', regex=True),
                        'fantasy_points': 0.0,
                        'fantasy_points_ppr': 0.0,
                        'games': 0,
                        'games_played': 0,
                        'age': 0,
                        'targets': 0,
                        'receptions': 0,
                        'carries': 0,
                        'rushing_yards': 0,
                        'receiving_yards': 0,
                        'passing_yards': 0,
                        'passing_tds': 0,
                        'rushing_tds': 0,
                        'receiving_tds': 0,
                        'interceptions': 0,
                        'rushing_fumbles': 0,
                        'rushing_fumbles_lost': 0,
                    })
                    df = pd.concat([df, projection_only_rows], ignore_index=True, sort=False)
                
                # Create a mapping from player_name to projection data
                bye_week_mapping = bye_week_df_clean.set_index('PLAYER NAME').to_dict('index')
                
                # Add projection data to main dataframe
                for col in [
                    'BYE WEEK', 'POS', 'TIERS', 'FANTASYPTS', 'RK',
                    'ADP', 'projection_method', 'source', 'team_conflict',
                ]:
                    df[col] = df['player_name'].map(
                        lambda x: bye_week_mapping.get(x, {}).get(col, 0)
                    )
                
                # Fill missing values
                df['BYE WEEK'] = df['BYE WEEK'].fillna('N/A')
                df['POS'] = df['POS'].fillna('Unknown')
                df['TIERS'] = df['TIERS'].fillna(99)
                df['FANTASYPTS'] = df['FANTASYPTS'].fillna(0)
                
                # Use projected position if available, otherwise keep historical position
                # Clean up position column to remove rank numbers (e.g., "WR1" -> "WR")
                df['POS'] = df['POS'].str.replace(r'\d+', '', regex=True)
                df['position'] = df['POS'].where(df['POS'] != 'Unknown', df['position'])
                
                # Convert fantasy points to numeric
                df['FANTASYPTS'] = pd.to_numeric(df['FANTASYPTS'], errors='coerce').fillna(0)
                df['projected_fantasy_points'] = df['FANTASYPTS']
                df['projection_tier'] = df['TIERS']
                df['projection_rank'] = pd.to_numeric(df['RK'], errors='coerce').fillna(999)
                
                logger.info(f"Added {self.target_season} projection/bye week data for {len(df[df['BYE WEEK'] != 'N/A'])} players")
                
            # Fallback to original projections if no bye week data
            elif projections_df is not None:
                logger.info("Merging with original target-season projections...")
                # Handle duplicate player names in projections by keeping the first occurrence
                projections_df_clean = projections_df.drop_duplicates(subset=['name'], keep='first')
                logger.info(f"Removed {len(projections_df) - len(projections_df_clean)} duplicate player names from projections")
                
                # Create a mapping from player_name to target-season projections
                projection_mapping = projections_df_clean.set_index('name').to_dict('index')
                
                # Add target-season projections to main dataframe
                for col in ['projected_fantasy_points', 'projection_tier', 'projection_rank', 'projected_pass_yards', 
                           'projected_pass_tds', 'projected_rec', 'projected_rec_yards', 
                           'projected_rec_tds', 'projected_rush_att', 'projected_rush_yards', 
                           'projected_rush_tds']:
                    df[col] = df['player_name'].map(
                        lambda x: projection_mapping.get(x, {}).get(col, 0)
                    )
                
                # Fill missing projections with 0
                for col in ['projected_fantasy_points', 'projected_pass_yards', 'projected_pass_tds', 
                           'projected_rec', 'projected_rec_yards', 'projected_rec_tds', 
                           'projected_rush_att', 'projected_rush_yards', 'projected_rush_tds']:
                    df[col] = df[col].fillna(0)
                
                # Fill missing tier and rank with defaults
                df['projection_tier'] = df['projection_tier'].fillna(99)
                df['projection_rank'] = df['projection_rank'].fillna(999)
                
                # Add default bye week column
                df['BYE WEEK'] = 'N/A'
                
                logger.info(f"Added target-season projections for {len(df[df['projected_fantasy_points'] > 0])} players")
            else:
                # If no projections, use current fantasy points as projections
                df['projected_fantasy_points'] = df['fantasy_points']
                df['projection_tier'] = 99
                df['projection_rank'] = 999
                df['BYE WEEK'] = 'N/A'
                self.projection_source = "historical_fantasy_points_fallback"
                logger.warning("No target-season projections found, using historical fantasy points as projections")
            
            # Standardize column names
            column_mapping = {
                'player_name': 'name',
                'fantasy_points': 'total_points',
                'fantasy_points_ppr': 'fantasy_points_ppr',
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
                'projected_fantasy_points': 0.0,
                'projection_tier': 99,
                'projection_rank': 999,
                'weighted_historical_points': 0.0,
                'historical_consistency_score': 50.0,
                'historical_seasons_count': 0,
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
                'fumbles_lost': 0,
                'BYE WEEK': 'N/A'
            }
            
            for col, default_val in required_columns.items():
                if col not in df.columns:
                    df[col] = default_val
            
            # Convert numeric columns
            numeric_columns = ['age', 'projected_fantasy_points', 'projection_tier', 'projection_rank',
                              'weighted_historical_points', 'historical_consistency_score',
                              'historical_seasons_count',
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

            # Filter to players with projections or fantasy points
            if 'projected_fantasy_points' in df.columns:
                df = df[df['projected_fantasy_points'] > 0].copy()
            elif 'fantasy_points' in df.columns:
                df = df[df['fantasy_points'] > 0].copy()

            df['position'] = df['position'].astype(str).str.replace(r'\d+', '', regex=True)
            df = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
            df = df[df['name'].notna() & (df['name'].astype(str).str.lower() != 'nan')].copy()
            df = self.merge_news_features(df)
            
            logger.info(f"Final dataset has {len(df)} players")
            return df
            
        except Exception as e:
            logger.error(f"Error in load_data: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return pd.DataFrame()

    def build_historical_features(self, historical_df: pd.DataFrame, seasons: int = 2) -> pd.DataFrame:
        """Create per-player historical scoring and consistency features before deduping."""
        if historical_df.empty or 'player_name' not in historical_df.columns or 'season' not in historical_df.columns:
            return pd.DataFrame()

        df = historical_df.copy()
        points_col = 'fantasy_points_ppr' if 'fantasy_points_ppr' in df.columns else 'fantasy_points'
        if points_col not in df.columns:
            return pd.DataFrame()

        df[points_col] = pd.to_numeric(df[points_col], errors='coerce').fillna(0)
        df['season'] = pd.to_numeric(df['season'], errors='coerce')
        df = df.dropna(subset=['player_name', 'season'])
        if df.empty:
            return pd.DataFrame()

        consistency_source = (
            pd.to_numeric(df.get('consistency_score', 0), errors='coerce').fillna(0)
            if 'consistency_score' in df.columns
            else pd.Series(0, index=df.index)
        )
        df['_normalized_consistency'] = consistency_source.clip(lower=0, upper=5) * 20

        latest_seasons = sorted(df['season'].dropna().unique(), reverse=True)[:seasons]
        recent = df[df['season'].isin(latest_seasons)].copy()
        recent = recent.sort_values(['player_name', 'season'], ascending=[True, False])

        weights = [0.6, 0.4] if seasons == 2 else []
        feature_rows = []
        for player_name, player_history in recent.groupby('player_name'):
            player_history = player_history.sort_values('season', ascending=False).head(seasons)
            effective_weights = weights[:len(player_history)]
            if not effective_weights:
                effective_weights = [1.0 / len(player_history)] * len(player_history)
            weight_sum = sum(effective_weights)
            effective_weights = [weight / weight_sum for weight in effective_weights]

            weighted_points = sum(
                float(row[points_col]) * effective_weights[idx]
                for idx, (_, row) in enumerate(player_history.iterrows())
            )
            weighted_consistency = sum(
                float(row['_normalized_consistency']) * effective_weights[idx]
                for idx, (_, row) in enumerate(player_history.iterrows())
            )
            feature_row = {
                'player_name': player_name,
                'weighted_historical_points': weighted_points,
                'historical_consistency_score': weighted_consistency,
                'historical_seasons_count': int(len(player_history)),
            }
            for _, row in player_history.iterrows():
                season = int(row['season'])
                feature_row[f'points_{season}'] = float(row[points_col])
            feature_rows.append(feature_row)

        features = pd.DataFrame(feature_rows).fillna(0)
        logger.info(
            "Built historical features from seasons %s for %s players",
            latest_seasons,
            len(features),
        )
        return features

    def load_news_features(self) -> pd.DataFrame:
        """Load optional player news features produced by news_analyzer.py."""
        news_file = self.news_dir / "player_features.json"
        if not news_file.exists():
            self.news_source = "none"
            logger.info("No news features found at %s", news_file)
            return pd.DataFrame()

        try:
            with open(news_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            logger.warning("Could not load news features from %s: %s", news_file, e)
            return pd.DataFrame()

        player_features = payload.get("player_features", {}) if isinstance(payload, dict) else {}
        rows = []
        for player_name, features in player_features.items():
            if not isinstance(features, dict):
                continue
            rows.append(
                {
                    "name": str(features.get("player", player_name)),
                    "news_sentiment_score": float(features.get("avg_sentiment", features.get("sentiment_score", 0)) or 0),
                    "news_buzz_score": float(features.get("avg_buzz", features.get("buzz_score", 0)) or 0),
                    "news_headline_count": int(features.get("headline_count", 0) or 0),
                    "news_injury_flag": bool(features.get("has_injury", features.get("injury_flag", False))),
                    "news_role_change_flag": bool(features.get("has_role_change", features.get("role_change", False))),
                    "news_topics": features.get("all_topics", features.get("topics", [])) or [],
                }
            )

        if not rows:
            return pd.DataFrame()

        news_df = pd.DataFrame(rows)
        news_df["news_key"] = news_df["name"].str.lower().str.strip()
        self.news_source = str(news_file)
        logger.info("Loaded news features for %s players from %s", len(news_df), news_file)
        return news_df

    def merge_news_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Merge optional news features onto the ranking dataframe by player name."""
        df = df.copy()
        news_df = self.load_news_features()
        default_columns = {
            "news_sentiment_score": 0.0,
            "news_buzz_score": 0.0,
            "news_headline_count": 0,
            "news_injury_flag": False,
            "news_role_change_flag": False,
            "news_topics": [],
        }

        if news_df.empty:
            for col, default in default_columns.items():
                df[col] = [default.copy() if isinstance(default, list) else default for _ in range(len(df))]
            return df

        df["news_key"] = df["name"].astype(str).str.lower().str.strip()
        merged = pd.merge(
            df,
            news_df.drop(columns=["name"]),
            on="news_key",
            how="left",
        ).drop(columns=["news_key"])

        for col, default in default_columns.items():
            if col not in merged.columns:
                merged[col] = [default.copy() if isinstance(default, list) else default for _ in range(len(merged))]
            elif isinstance(default, list):
                merged[col] = merged[col].apply(lambda value: value if isinstance(value, list) else [])
            elif isinstance(default, bool):
                merged[col] = merged[col].fillna(default).astype(bool)
            else:
                merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(default)

        matched_count = int((merged["news_headline_count"] > 0).sum())
        logger.info("Merged news features onto %s ranked players", matched_count)
        return merged

    def _process_projection_file(self, projections_df: pd.DataFrame) -> pd.DataFrame:
        """Process the target-season projections CSV to standardize format"""
        try:
            logger.info("Processing target-season projections data...")
            
            # Rename columns to match expected format
            column_mapping = {
                'RK': 'projection_rank',
                'TIERS': 'projection_tier', 
                'PLAYER NAME': 'name',
                'TEAM': 'team',
                'FANTASYPTS': 'projected_fantasy_points'
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
            logger.error(f"Error processing target-season projections: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return pd.DataFrame()

    def _process_projection_bye_week_data(self, bye_week_df: pd.DataFrame) -> pd.DataFrame:
        """Process target-season projection/bye week data CSV to standardize format."""
        try:
            logger.info(f"Processing {self.target_season} projection/bye week data...")

            season_neutral_mapping = {
                'name': 'PLAYER NAME',
                'player': 'PLAYER NAME',
                'player_name': 'PLAYER NAME',
                'position': 'POS',
                'pos': 'POS',
                'team': 'TEAM',
                'bye_week': 'BYE WEEK',
                'bye': 'BYE WEEK',
                'projected_fantasy_points': 'FANTASYPTS',
                'projected_points': 'FANTASYPTS',
                'fantasy_points': 'FANTASYPTS',
                'fpts': 'FANTASYPTS',
                'tier': 'TIERS',
                'tiers': 'TIERS',
                'rank': 'RK',
                'adp': 'ADP',
            }
            legacy_year = self.target_season - 1
            season_neutral_mapping[f'projected_{legacy_year}_pts'] = 'FANTASYPTS'
            season_neutral_mapping[f'tier_{legacy_year}'] = 'TIERS'
            season_neutral_mapping[f'rank_{legacy_year}'] = 'RK'
            rename_columns = {}
            for col in bye_week_df.columns:
                normalized = str(col).strip().lower().replace(' ', '_')
                if normalized in season_neutral_mapping:
                    rename_columns[col] = season_neutral_mapping[normalized]
            bye_week_df = bye_week_df.rename(columns=rename_columns)
            
            # Clean up the data
            bye_week_df = bye_week_df.dropna(subset=['PLAYER NAME'])

            for col, default_value in {
                'RK': 999,
                'POS': 'Unknown',
                'TEAM': 'Unknown',
                'BYE WEEK': 'N/A',
                'TIERS': 99,
                'FANTASYPTS': 0,
                'ADP': 999,
                'projection_method': 'unknown',
                'source': 'unknown',
                'team_conflict': False,
            }.items():
                if col not in bye_week_df.columns:
                    bye_week_df[col] = default_value
            
            # Convert bye week to string and handle any non-numeric values
            bye_week_df['BYE WEEK'] = bye_week_df['BYE WEEK'].astype(str)
            bye_week_df['POS'] = bye_week_df['POS'].astype(str)
            bye_week_df['TEAM'] = bye_week_df['TEAM'].fillna('Unknown').astype(str)
            
            # Convert tiers to numeric
            bye_week_df['TIERS'] = pd.to_numeric(bye_week_df['TIERS'], errors='coerce').fillna(99)
            
            # Prefer real projected points when present. Legacy bye-only files fall back to a rank estimate.
            bye_week_df['FANTASYPTS'] = pd.to_numeric(bye_week_df['FANTASYPTS'], errors='coerce')
            missing_points = bye_week_df['FANTASYPTS'].isna() | (bye_week_df['FANTASYPTS'] <= 0)
            if missing_points.any():
                rank_estimate = 300 - (pd.to_numeric(bye_week_df['RK'], errors='coerce').fillna(500) * 0.5)
                bye_week_df.loc[missing_points, 'FANTASYPTS'] = rank_estimate[missing_points]
            bye_week_df['FANTASYPTS'] = bye_week_df['FANTASYPTS'].fillna(0)
            
            logger.info(f"Processed {len(bye_week_df)} bye week records")
            logger.info(f"Bye week distribution: {bye_week_df['BYE WEEK'].value_counts().to_dict()}")
            
            return bye_week_df
            
        except Exception as e:
            logger.error(f"Error processing projection bye week data: {e}")
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
        """Calculate weighted average of recent historical fantasy points."""
        weighted_historical_points = float(row.get('weighted_historical_points', 0))
        if weighted_historical_points > 0:
            return weighted_historical_points

        # Legacy fallback for older test fixtures and ranking files.
        points_2024 = float(row.get('points_2024', 0))
        points_2023 = float(row.get('points_2023', 0))
        if points_2024 > 0 and points_2023 > 0:
            return 0.6 * points_2024 + 0.4 * points_2023
        elif points_2024 > 0:
            return points_2024
        elif points_2023 > 0:
            return points_2023
        else:
            return 0.0
    
    def calculate_consistency_score(self, row: pd.Series) -> float:
        """Return a 0-100 consistency score from weekly historical production."""
        historical_consistency = float(row.get('historical_consistency_score', 0))
        if historical_consistency > 0:
            return max(0, min(100, historical_consistency))

        legacy_consistency = float(row.get('consistency_score', 0))
        if legacy_consistency > 0:
            return max(0, min(100, legacy_consistency * 20))

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

    def calculate_news_adjustment(self, row: pd.Series) -> float:
        """Calculate a small, explainable news adjustment."""
        sentiment = max(-1.0, min(1.0, float(row.get('news_sentiment_score', 0) or 0)))
        buzz = max(0.0, min(1.0, float(row.get('news_buzz_score', 0) or 0)))
        headline_count = max(0, int(row.get('news_headline_count', 0) or 0))
        injury_flag = bool(row.get('news_injury_flag', False))
        role_change_flag = bool(row.get('news_role_change_flag', False))

        if headline_count == 0:
            return 0.0

        adjustment = sentiment * 4.0
        if sentiment >= 0:
            adjustment += buzz * 2.0
        else:
            adjustment += sentiment * buzz * 2.0
        if role_change_flag:
            adjustment += 3.0 if sentiment >= 0 else -3.0
        if injury_flag:
            adjustment -= 12.0

        return max(-15.0, min(6.0, adjustment))
    
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
        """Calculate raw score using the weighted formula with target-season projections"""
        features = self.build_score_features(row)
        return sum(features[col] for col in self.score_feature_columns)

    def build_score_features(self, row: pd.Series) -> Dict[str, float]:
        """Build the explicit, weighted score components for one player."""
        projected_fantasy_points = float(row.get('projected_fantasy_points', 0))
        projection_tier = float(row.get('projection_tier', 99))
        projection_rank = float(row.get('projection_rank', 999))

        dampened_projection = self.dampen_inflated_projections(row, projected_fantasy_points)
        weighted_history = self.calculate_weighted_historical_average(row)
        consistency_score = self.calculate_consistency_score(row)
        usage_score = self.calculate_usage_score(row)
        team_offense_score = self.calculate_team_offense_score(row)
        tier_score = self.calculate_tier_score(projection_tier)
        rank_score = self.calculate_rank_score(projection_rank)
        news_adjustment = self.calculate_news_adjustment(row)

        return {
            'projected_points_component': self.weights['projected_fantasy_points'] * dampened_projection,
            'historical_points_component': self.weights['weighted_avg_last_2'] * weighted_history,
            'consistency_component': self.weights['consistency_score'] * consistency_score,
            'usage_component': self.weights['usage_score'] * usage_score,
            'team_offense_component': self.weights['team_offense_score'] * team_offense_score,
            'projection_tier_component': 0.15 * tier_score,
            'projection_rank_component': 0.10 * rank_score,
            'news_component': news_adjustment,
        }

    def add_score_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add score component columns and raw_score to the ranking dataframe."""
        df = df.copy()
        feature_rows = df.apply(self.build_score_features, axis=1, result_type='expand')
        for col in self.score_feature_columns:
            df[col] = pd.to_numeric(feature_rows[col], errors='coerce').fillna(0)
        df['raw_score'] = df[self.score_feature_columns].sum(axis=1)
        return df
    
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
        projected_pts = float(row.get('projected_fantasy_points', 0))
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
        """Assign tiers based on target-season projections and VORP percentiles"""
        df = df.copy()
        
        # First, use projection tier information if available
        if 'projection_tier' in df.columns:
            logger.info("Using projection tier information for initial tier assignment...")
            # Convert numeric tier to tier name
            df['tier'] = df['projection_tier'].apply(self._convert_tier_number_to_name)
        
        # Calculate tiers for each position based on VORP for players without projection tiers
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_df = df[df['position'] == position].copy()
            if len(pos_df) == 0:
                continue
            
            # For players without projection tier info, calculate based on VORP
            pos_df_no_tier = pos_df[pos_df['tier'] == 'Tier 5'].copy()
            if len(pos_df_no_tier) > 0:
                # Sort by VORP
                pos_df_no_tier = pos_df_no_tier.sort_values('VORP', ascending=False)
                
                # Assign tiers based on percentiles
                tier_names = ['Tier 1', 'Tier 2', 'Tier 3', 'Tier 4']
                for tier_name in tier_names:
                    percentile = self.tier_percentiles[tier_name]
                    if percentile > 0:
                        cutoff_idx = int(len(pos_df_no_tier) * percentile)
                        if cutoff_idx > 0:
                            pos_df_no_tier.iloc[:cutoff_idx, pos_df_no_tier.columns.get_loc('tier')] = tier_name
                
                # Update main dataframe using original row indices.
                df.loc[pos_df_no_tier.index, 'tier'] = pos_df_no_tier['tier']
        
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
        """Generate flags for player based on target-season projections and historical data"""
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
        projected_pts = float(row.get('projected_fantasy_points', 0))
        if age <= 25 and projected_pts > 200:
            flags.append("High Upside")
        
        # Age risk flag
        if age >= 30:
            flags.append("Age Risk")
        
        # target-season projection flags
        projection_tier = float(row.get('projection_tier', 99))
        projection_rank = float(row.get('projection_rank', 999))
        
        # Elite tier flag
        if projection_tier <= 1:
            flags.append("Elite Tier")
        
        # Top 10 rank flag
        if projection_rank <= 10:
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
            
            # Calculate raw scores from explicit feature components
            logger.info("Calculating score features and raw scores...")
            current_stats_df = self.add_score_features(current_stats_df)
            
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
            
            # Select top players. Keep the full projection board by default so the
            # draft recommender has enough RB/WR depth for position-specific picks.
            if self.max_players > 0 and len(current_stats_df) > self.max_players:
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
                projection_rank = row.get('projection_rank', 999)
                projection_tier = row.get('projection_tier', 99)
                age = row.get('age', 0)
                projection_rank = 999 if pd.isna(projection_rank) else int(projection_rank)
                projection_tier = 99 if pd.isna(projection_tier) else int(projection_tier)
                age = 0 if pd.isna(age) else int(age)
                player_data = {
                    "name": row.get('name', 'Unknown'),
                    "pos": row.get('position', 'Unknown'),
                    "team": row.get('team', 'Unknown'),
                    "score": round(row.get('adjusted_score', 0), 2),
                    "VORP": round(row.get('VORP', 0), 2),
                    "tier": row.get('tier', 'Tier 5'),
                    "age": age,
                    "injury_risk": "Low",  # Simplified for now
                    "flags": row.get('flags', []),
                    "projected_fantasy_points": round(row.get('projected_fantasy_points', 0), 1),
                    "projection_rank": projection_rank,
                    "projection_tier": projection_tier,
                    "adp": round(float(row.get('ADP', 999)), 2) if not pd.isna(row.get('ADP', 999)) else None,
                    "projection_method": str(row.get('projection_method', 'unknown')),
                    "projection_data_source": str(row.get('source', 'unknown')),
                    "team_conflict": bool(row.get('team_conflict', False)),
                    "weighted_historical_points": round(row.get('weighted_historical_points', 0), 1),
                    "historical_consistency_score": round(row.get('historical_consistency_score', 0), 1),
                    "historical_seasons_count": int(row.get('historical_seasons_count', 0) or 0),
                    "news_sentiment_score": round(row.get('news_sentiment_score', 0), 3),
                    "news_buzz_score": round(row.get('news_buzz_score', 0), 3),
                    "news_headline_count": int(row.get('news_headline_count', 0) or 0),
                    "news_injury_flag": bool(row.get('news_injury_flag', False)),
                    "news_role_change_flag": bool(row.get('news_role_change_flag', False)),
                    "news_topics": row.get('news_topics', []),
                    "raw_score": round(row.get('raw_score', 0), 2),
                    "score_breakdown": {
                        col: round(row.get(col, 0), 2)
                        for col in self.score_feature_columns
                    },
                    "bye_week": str(row.get('BYE WEEK', 'N/A'))
                }
                output_data.append(player_data)
            
            export_payload = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "target_season": self.target_season,
                    "projection_source": self.projection_source,
                    "news_source": self.news_source,
                    "ranking_count": len(output_data),
                },
                "rankings": output_data,
            }

            # Save to file
            output_file = self.outputs_dir / f"player_rankings.json"
            with open(output_file, 'w') as f:
                json.dump(export_payload, f, indent=2)
            
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
                  f"Flags: {row['flags']} Bye: {row['BYE WEEK']}")
    
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
                print(f"    {row['name']:<15} VORP: {row['VORP']:5.1f} Score: {row['adjusted_score']:6.1f} Bye: {row['BYE WEEK']}")

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
        ranker.print_top_rankings(rankings_df, top_n=50)
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

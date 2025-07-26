#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Player Ranking Module
Phase 4: Combine stats + news features into final rankings

This module creates comprehensive player rankings by blending:
- Historical fantasy performance (exponential moving average)
- Injury risk assessment
- Experience level considerations (rookies vs veterans)
- Team context and performance
- Recent news sentiment and buzz
- Consistency metrics
"""

import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PlayerRanker:
    """Comprehensive player ranking system for fantasy football"""
    
    def __init__(self, data_dir: str = "data", news_dir: str = "news", outputs_dir: str = "outputs", max_players: int = 50):
        self.data_dir = Path(data_dir)
        self.news_dir = Path(news_dir)
        self.outputs_dir = Path(outputs_dir)
        self.max_players = max_players
        self.outputs_dir.mkdir(exist_ok=True)
        
        # Scoring weights (can be adjusted)
        self.weights = {
            'historical_performance': 0.30,  # Historical fantasy points (reduced from 0.35)
            'current_form': 0.25,            # Recent performance trend
            'injury_risk': -0.15,            # Injury proneness (negative)
            'experience_bonus': 0.10,        # Rookie/veteran considerations
            'team_context': 0.10,            # Team performance influence
            'news_sentiment': 0.10,          # Recent buzz and sentiment
            'consistency': 0.05,             # Weekly performance stability
            'ceiling_potential': 0.05        # NEW: High-ceiling upside potential
        }
        
        # Position-specific adjustments
        self.position_weights = {
            'QB': {'experience_bonus': 0.15, 'consistency': 0.10, 'ceiling_potential': 0.10},  # QBs benefit from experience and ceiling
            'RB': {'injury_risk': -0.20, 'current_form': 0.30, 'ceiling_potential': 0.15},     # RBs more injury-prone, form matters more, high ceiling
            'WR': {'news_sentiment': 0.15, 'team_context': 0.15, 'ceiling_potential': 0.10},   # WRs affected by team/QB changes
            'TE': {'experience_bonus': 0.05, 'consistency': 0.10, 'ceiling_potential': 0.05},  # TEs benefit from consistency
            'K': {'consistency': 0.20, 'team_context': 0.20},       # Kickers need consistency and good team
            'DST': {'team_context': 0.30, 'consistency': 0.15}      # Defense heavily team-dependent
        }
        
        # Team performance tiers (based on recent seasons)
        self.team_tiers = {
            'elite': ['KC', 'SF', 'BAL', 'BUF', 'DAL', 'PHI'],
            'good': ['MIA', 'DET', 'CIN', 'GB', 'LAR', 'HOU', 'IND'],
            'average': ['NYJ', 'ATL', 'MIN', 'JAX', 'TB', 'PIT', 'CLE'],
            'below_average': ['LV', 'LAC', 'DEN', 'NE', 'NYG', 'WAS', 'CHI'],
            'poor': ['ARI', 'CAR', 'TEN', 'SEA']
        }
        
        self.team_scores = {
            'elite': 1.2, 'good': 1.1, 'average': 1.0, 
            'below_average': 0.9, 'poor': 0.8
        }
        
    def load_data(self) -> Tuple[pd.DataFrame, Dict]:
        """Load player stats and news features"""
        try:
            # Try to load enhanced player stats first
            stats_file = self.data_dir / "enhanced_player_stats.csv"
            if not stats_file.exists():
                # Fallback to base player stats
                stats_file = self.data_dir / "base_player_stats.csv"
                if not stats_file.exists():
                    # Fallback to raw NFL data
                    stats_file = self.data_dir / "nfl_player_data.csv"
            
            if stats_file.exists():
                stats_df = pd.read_csv(stats_file)
                logger.info(f"Loaded {len(stats_df)} players from {stats_file.name}")
                
                # If max_players is specified and we have more players, filter to top performers
                if self.max_players is not None and len(stats_df) > self.max_players:
                    # Sort by fantasy points or total score if available
                    if 'total_fantasy_points' in stats_df.columns:
                        stats_df = stats_df.nlargest(self.max_players, 'total_fantasy_points')
                    elif 'points_2024' in stats_df.columns:
                        stats_df = stats_df.nlargest(self.max_players, 'points_2024')
                    else:
                        # Take first max_players
                        stats_df = stats_df.head(self.max_players)
                    
                    logger.info(f"Filtered to top {len(stats_df)} players")
                else:
                    logger.info(f"Ranking all {len(stats_df)} available players")
            else:
                # Create a minimal dataset if no files exist
                logger.warning("No player stats files found, creating minimal dataset")
                stats_df = self._create_minimal_dataset()
            
            # Load news features
            news_file = self.news_dir / "player_features.json"
            if news_file.exists():
                with open(news_file, 'r') as f:
                    news_data = json.load(f)
                logger.info(f"Loaded news features for {len(news_data.get('player_features', {}))} players")
            else:
                news_data = {'player_features': {}}
                logger.warning("No news features found, using empty data")
            
            return stats_df, news_data
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise
    
    def _create_minimal_dataset(self) -> pd.DataFrame:
        """Create a minimal dataset with top fantasy players"""
        # This is a fallback if no data files exist
        top_players = [
            {'player': 'Christian McCaffrey', 'position': 'RB', 'team': 'SF', 'points_2024': 320.5, 'age': 28, 'experience': 8},
            {'player': 'Tyreek Hill', 'position': 'WR', 'team': 'MIA', 'points_2024': 298.2, 'age': 30, 'experience': 8},
            {'player': 'Travis Kelce', 'position': 'TE', 'team': 'KC', 'points_2024': 245.6, 'age': 35, 'experience': 12},
            {'player': 'Patrick Mahomes', 'position': 'QB', 'team': 'KC', 'points_2024': 398.7, 'age': 29, 'experience': 8},
            {'player': 'Josh Allen', 'position': 'QB', 'team': 'BUF', 'points_2024': 425.3, 'age': 28, 'experience': 7},
            {'player': 'CeeDee Lamb', 'position': 'WR', 'team': 'DAL', 'points_2024': 275.8, 'age': 25, 'experience': 5},
            {'player': 'Bijan Robinson', 'position': 'RB', 'team': 'ATL', 'points_2024': 265.3, 'age': 22, 'experience': 2},
            {'player': 'Amon-Ra St. Brown', 'position': 'WR', 'team': 'DET', 'points_2024': 258.7, 'age': 24, 'experience': 4},
            {'player': 'Saquon Barkley', 'position': 'RB', 'team': 'PHI', 'points_2024': 245.9, 'age': 27, 'experience': 7},
            {'player': 'Sam LaPorta', 'position': 'TE', 'team': 'DET', 'points_2024': 198.3, 'age': 24, 'experience': 2},
        ]
        
        # Add more players to reach max_players
        additional_players = [
            {'player': 'Dak Prescott', 'position': 'QB', 'team': 'DAL', 'points_2024': 365.4, 'age': 31, 'experience': 9},
            {'player': 'Jalen Hurts', 'position': 'QB', 'team': 'PHI', 'points_2024': 385.2, 'age': 26, 'experience': 5},
            {'player': 'Lamar Jackson', 'position': 'QB', 'team': 'BAL', 'points_2024': 372.8, 'age': 27, 'experience': 7},
            {'player': 'Breece Hall', 'position': 'RB', 'team': 'NYJ', 'points_2024': 285.1, 'age': 23, 'experience': 3},
            {'player': 'Jonathan Taylor', 'position': 'RB', 'team': 'IND', 'points_2024': 232.1, 'age': 25, 'experience': 5},
            {'player': 'Garrett Wilson', 'position': 'WR', 'team': 'NYJ', 'points_2024': 238.4, 'age': 24, 'experience': 3},
            {'player': 'AJ Brown', 'position': 'WR', 'team': 'PHI', 'points_2024': 228.6, 'age': 27, 'experience': 6},
            {'player': 'Evan Engram', 'position': 'TE', 'team': 'JAX', 'points_2024': 176.2, 'age': 30, 'experience': 8},
            {'player': 'T.J. Hockenson', 'position': 'TE', 'team': 'MIN', 'points_2024': 187.5, 'age': 27, 'experience': 6},
            {'player': 'George Kittle', 'position': 'TE', 'team': 'SF', 'points_2024': 165.8, 'age': 31, 'experience': 8},
        ]
        
        all_players = top_players + additional_players
        
        # Create DataFrame with required columns
        df = pd.DataFrame(all_players)
        
        # Add missing columns with default values
        df['injury_score'] = 1.0
        df['consistency_score'] = 0.7
        df['weekly_avg'] = df['points_2024'] / 17  # Approximate weekly average
        df['weekly_std'] = df['weekly_avg'] * 0.3  # Approximate standard deviation
        df['experience_level'] = df['experience'].apply(lambda x: 'Rookie' if x <= 1 else 'Young' if x <= 4 else 'Veteran')
        
        return df
    
    def calculate_historical_performance_score(self, row: pd.Series) -> float:
        """Calculate exponential moving average of fantasy performance"""
        try:
            # Use 2024 points as current performance
            current_points = row.get('points_2024', 0)
            if pd.isna(current_points) or current_points == 0:
                return 0.0
            
            # For now, use current points as historical (can be enhanced with multi-year data)
            # In a full implementation, this would use actual historical data
            historical_score = current_points / 400.0  # Normalize to 0-1 scale (400 pts = elite season)
            return min(historical_score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating historical score for {row.get('player', 'Unknown')}: {e}")
            return 0.0
    
    def calculate_current_form_score(self, row: pd.Series) -> float:
        """Calculate current form based on recent performance trends"""
        try:
            # Use consistency score as a proxy for current form
            consistency = row.get('consistency_score', 0.5)
            weekly_avg = row.get('weekly_avg', 0)
            
            # Normalize weekly average (20+ points per week = elite)
            avg_score = min(weekly_avg / 20.0, 1.0)
            
            # Combine consistency and average performance
            form_score = (consistency * 0.6) + (avg_score * 0.4)
            return form_score
            
        except Exception as e:
            logger.warning(f"Error calculating form score for {row.get('player', 'Unknown')}: {e}")
            return 0.5
    
    def calculate_injury_risk_score(self, row: pd.Series) -> float:
        """Calculate injury risk as a negative score"""
        try:
            # Base injury score (1 = healthy, 0 = injured)
            base_injury = row.get('injury_score', 1.0)
            
            # Age factor (older players more injury-prone)
            age = row.get('age', 25)
            age_risk = max(0, (age - 25) / 10)  # 0 at age 25, 1 at age 35+
            
            # Experience factor (very young players can be injury-prone)
            experience = row.get('experience', 3)
            exp_risk = max(0, (3 - experience) / 3)  # 0 at 3+ years, 1 at rookie
            
            # Position-specific injury risk
            position = row.get('position', 'WR')
            position_risk = {
                'RB': 0.3, 'WR': 0.1, 'TE': 0.2, 'QB': 0.1, 'K': 0.0, 'DST': 0.0
            }.get(position, 0.1)
            
            # Combine factors
            total_risk = (base_injury * 0.4) + (age_risk * 0.2) + (exp_risk * 0.2) + (position_risk * 0.2)
            return 1.0 - total_risk  # Convert to positive score (1 = low risk)
            
        except Exception as e:
            logger.warning(f"Error calculating injury risk for {row.get('player', 'Unknown')}: {e}")
            return 0.8
    
    def calculate_experience_bonus(self, row: pd.Series) -> float:
        """Calculate experience bonus for rookies and veterans"""
        try:
            experience = row.get('experience', 3)
            experience_level = row.get('experience_level', 'Young')
            position = row.get('position', 'WR')
            
            # Rookie bonus (high potential, but risky)
            if experience <= 1:
                rookie_bonus = 0.2 if position in ['RB', 'WR'] else 0.1
                return rookie_bonus
            
            # Veteran bonus (proven track record)
            elif experience >= 5:
                vet_bonus = 0.1 if position in ['QB', 'TE'] else 0.05
                return vet_bonus
            
            # Young player (2-4 years) - slight bonus
            else:
                return 0.05
                
        except Exception as e:
            logger.warning(f"Error calculating experience bonus for {row.get('player', 'Unknown')}: {e}")
            return 0.0
    
    def calculate_team_context_score(self, row: pd.Series) -> float:
        """Calculate team context score based on team performance"""
        try:
            team = row.get('team', 'Unknown')
            position = row.get('position', 'WR')
            
            # Find team tier
            team_tier = 'average'
            for tier, teams in self.team_tiers.items():
                if team in teams:
                    team_tier = tier
                    break
            
            base_score = self.team_scores.get(team_tier, 1.0)
            
            # Position-specific team adjustments
            if position == 'QB':
                # QBs benefit more from good teams
                return base_score
            elif position == 'RB':
                # RBs can succeed on bad teams too
                return 0.9 + (base_score - 1.0) * 0.5
            elif position == 'WR':
                # WRs heavily dependent on QB/team
                return base_score
            elif position == 'TE':
                # TEs benefit from good QBs
                return base_score
            elif position == 'K':
                # Kickers need good offenses
                return base_score
            elif position == 'DST':
                # Defense IS the team
                return base_score
            else:
                return base_score
                
        except Exception as e:
            logger.warning(f"Error calculating team context for {row.get('player', 'Unknown')}: {e}")
            return 1.0
    
    def calculate_news_sentiment_score(self, row: pd.Series, news_data: Dict) -> float:
        """Calculate news sentiment score from recent headlines"""
        try:
            player_name = row.get('player', '')
            player_features = news_data.get('player_features', {}).get(player_name, {})
            
            if not player_features:
                return 0.5  # Neutral if no news
            
            # Get sentiment and buzz scores
            avg_sentiment = player_features.get('avg_sentiment', 0.5)
            avg_buzz = player_features.get('avg_buzz', 0.5)
            has_injury = player_features.get('has_injury', False)
            has_role_change = player_features.get('has_role_change', False)
            
            # Base score from sentiment and buzz
            base_score = (avg_sentiment * 0.6) + (avg_buzz * 0.4)
            
            # Adjust for negative factors
            if has_injury:
                base_score *= 0.7  # 30% penalty for injury news
            
            # Adjust for role changes (can be positive or negative)
            if has_role_change:
                # Assume role changes are generally positive for fantasy
                base_score *= 1.1
            
            return min(base_score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating news sentiment for {row.get('player', 'Unknown')}: {e}")
            return 0.5
    
    def calculate_consistency_score(self, row: pd.Series) -> float:
        """Calculate consistency score based on weekly performance stability"""
        try:
            consistency = row.get('consistency_score', 0.5)
            return consistency
            
        except Exception as e:
            logger.warning(f"Error calculating consistency for {row.get('player', 'Unknown')}: {e}")
            return 0.5
    
    def calculate_ceiling_potential(self, row: pd.Series) -> float:
        """Calculate ceiling potential based on historical high games and recent trends"""
        try:
            position = row.get('position', 'WR')
            
            # Get available data
            weekly_avg = row.get('weekly_avg', 0)
            weekly_std = row.get('weekly_std', 0)
            consistency_score = row.get('consistency_score', 0.5)
            
            if weekly_avg == 0:
                return 0.5
            
            # Estimate ceiling based on standard deviation (higher std = higher ceiling potential)
            if weekly_std > 0:
                # Calculate potential ceiling as avg + 2*std
                estimated_ceiling = weekly_avg + (2 * weekly_std)
                ceiling_ratio = estimated_ceiling / weekly_avg
            else:
                ceiling_ratio = 1.5  # Default if no std data
            
            # Position-specific ceiling expectations
            position_ceilings = {
                'QB': 1.8,  # QBs can have 1.8x their average in great games
                'RB': 2.0,  # RBs can have 2x their average in great games
                'WR': 2.2,  # WRs can have 2.2x their average in great games
                'TE': 1.6,  # TEs are more consistent, lower ceiling
                'K': 1.3,   # Kickers are very consistent
                'DST': 1.5  # Defenses can have big games
            }
            
            expected_ceiling = position_ceilings.get(position, 1.5)
            
            # Score based on how close they are to expected ceiling
            ceiling_score = min(ceiling_ratio / expected_ceiling, 1.0)
            
            # Bonus for young players (higher potential)
            experience = row.get('experience', 3)
            if experience <= 2:
                ceiling_score *= 1.2  # 20% bonus for young players
            
            # Penalty for very consistent players (lower ceiling potential)
            if consistency_score > 0.8:
                ceiling_score *= 0.9  # 10% penalty for very consistent players
            
            return min(ceiling_score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating ceiling potential for {row.get('player', 'Unknown')}: {e}")
            return 0.5
    
    def calculate_total_score(self, row: pd.Series, news_data: Dict) -> float:
        """Calculate total ranking score for a player"""
        try:
            position = row.get('position', 'WR')
            
            # Get position-specific weights
            pos_weights = self.position_weights.get(position, {})
            weights = self.weights.copy()
            weights.update(pos_weights)
            
            # Calculate individual scores
            scores = {
                'historical_performance': self.calculate_historical_performance_score(row),
                'current_form': self.calculate_current_form_score(row),
                'injury_risk': self.calculate_injury_risk_score(row),
                'experience_bonus': self.calculate_experience_bonus(row),
                'team_context': self.calculate_team_context_score(row),
                'news_sentiment': self.calculate_news_sentiment_score(row, news_data),
                'consistency': self.calculate_consistency_score(row),
                'ceiling_potential': self.calculate_ceiling_potential(row)
            }
            
            # Calculate weighted total
            total_score = sum(scores[component] * weights[component] for component in scores)
            
            # Normalize to 0-100 scale
            total_score = total_score * 100
            
            return total_score
            
        except Exception as e:
            logger.error(f"Error calculating total score for {row.get('player', 'Unknown')}: {e}")
            return 0.0
    
    def calculate_vorp_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate VORP (Value Over Replacement Player) scores"""
        try:
            # Step 1: Define replacement level rank per position
            # These represent the "replacement level" player you can get on waivers
            replacement_ranks = {
                'QB': 15,    # QB12 is typically available on waivers
                'RB': 20,    # RB24 is replacement level (flex play)
                'WR': 30,    # WR30 is replacement level (flex play)
                'TE': 12,    # TE12 is replacement level
                'K': 12,     # K12 is replacement level
                'DST': 12    # DST12 is replacement level
            }
            
            # Step 2: Compute baseline scores per position
            baseline_scores = {}
            for pos in df['position'].unique():
                pos_df = df[df['position'] == pos].copy()
                baseline_rank = replacement_ranks.get(pos, 12)
                
                if len(pos_df) >= baseline_rank:
                    # Get the score of the replacement level player
                    pos_df_sorted = pos_df.nlargest(baseline_rank, 'total_score')
                    baseline_score = pos_df_sorted.iloc[-1]['total_score']
                    baseline_scores[pos] = baseline_score
                else:
                    # Fallback to median if not enough players
                    baseline_scores[pos] = pos_df['total_score'].median()
                
                logger.info(f"Position {pos}: replacement level score = {baseline_scores[pos]:.2f}")
            
            # Step 3: Calculate VORP score for each player
            df['baseline_score'] = df['position'].map(baseline_scores)
            df['vorp_score'] = df['total_score'] - df['baseline_score']
            
            # Step 4: Calculate VORP rank (more important than raw rank for drafting)
            df['vorp_rank'] = df.groupby('position')['vorp_score'].rank(method='dense', ascending=False)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating VORP scores: {e}")
            return df
    
    def assign_tiers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Assign tiers based on VORP score using constant thresholds"""
        try:
            def get_tier_from_vorp(vorp_score):
                """Assign tier based on VORP score using constant thresholds"""
                if vorp_score >= 15:
                    return 1
                elif vorp_score >= 10:
                    return 2
                elif vorp_score >= 5:
                    return 3
                elif vorp_score >= 0:
                    return 4
                else:
                    return 5
            
            # Apply tier assignment based on VORP scores
            df['tier'] = df['vorp_score'].apply(get_tier_from_vorp)
            
            # Log tier distribution for analysis
            tier_counts = df['tier'].value_counts().sort_index()
            logger.info(f"Tier distribution: {dict(tier_counts)}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error assigning tiers: {e}")
            return df
    
    def rank_players(self) -> pd.DataFrame:
        """Main ranking function"""
        try:
            logger.info("Starting player ranking process...")
            
            # Load data
            stats_df, news_data = self.load_data()
            
            # Calculate total scores
            logger.info("Calculating player scores...")
            stats_df['total_score'] = stats_df.apply(
                lambda row: self.calculate_total_score(row, news_data), axis=1
            )
            
            # Add ceiling potential column
            stats_df['ceiling_potential'] = stats_df.apply(
                lambda row: self.calculate_ceiling_potential(row), axis=1
            )
            
            # Calculate VORP scores
            logger.info("Calculating VORP scores...")
            stats_df = self.calculate_vorp_scores(stats_df)
            
            # Sort by VORP score within each position (more relevant for drafting)
            stats_df = stats_df.sort_values(['position', 'vorp_score'], ascending=[True, False])
            
            # Assign ranks within positions based on VORP
            stats_df['rank'] = stats_df.groupby('position')['vorp_score'].rank(method='dense', ascending=False)
            
            # Assign tiers based on VORP
            stats_df = self.assign_tiers(stats_df)
            
            # Add metadata
            stats_df['ranked_at'] = datetime.now().isoformat()
            
            logger.info(f"Ranking complete. Processed {len(stats_df)} players.")
            return stats_df
            
        except Exception as e:
            logger.error(f"Error in ranking process: {e}")
            raise
    
    def export_rankings(self, df: pd.DataFrame) -> None:
        """Export rankings to CSV files by position"""
        try:
            logger.info("Exporting rankings...")
            
            # Export overall rankings
            overall_file = self.outputs_dir / "ranked_all_players.csv"
            df.to_csv(overall_file, index=False)
            logger.info(f"Exported overall rankings to {overall_file}")
            
            # Export by position
            for position in df['position'].unique():
                pos_df = df[df['position'] == position].copy()
                pos_file = self.outputs_dir / f"ranked_{position}.csv"
                pos_df.to_csv(pos_file, index=False)
                logger.info(f"Exported {position} rankings to {pos_file}")
            
            # Create ranking summary with position scarcity analysis
            self.create_ranking_summary(df)
            
        except Exception as e:
            logger.error(f"Error exporting rankings: {e}")
            raise
    
    def create_ranking_summary(self, df: pd.DataFrame) -> None:
        """Create comprehensive ranking summary with VORP and position scarcity analysis"""
        try:
            summary = {
                'total_players': len(df),
                'positions': df['position'].value_counts().to_dict(),
                'tiers': df['tier'].value_counts().to_dict(),
                'ranked_at': datetime.now().isoformat(),
                'vorp_analysis': {},
                'top_players_by_position': {},
                'position_scarcity': {},
                'risk_reward_players': [],
                'undervalued_players': [],
                'best_values_by_vorp': []
            }
            
            # VORP analysis by position
            for position in df['position'].unique():
                pos_df = df[df['position'] == position]
                baseline_score = pos_df['baseline_score'].iloc[0] if len(pos_df) > 0 else 0
                
                summary['vorp_analysis'][position] = {
                    'baseline_score': baseline_score,
                    'max_vorp': pos_df['vorp_score'].max() if len(pos_df) > 0 else 0,
                    'avg_vorp': pos_df['vorp_score'].mean() if len(pos_df) > 0 else 0,
                    'players_above_baseline': len(pos_df[pos_df['vorp_score'] > 0])
                }
            
            # Top players by position (now including VORP)
            for position in df['position'].unique():
                pos_df = df[df['position'] == position].head(5)
                summary['top_players_by_position'][position] = [
                    {
                        'player': row['player'],
                        'team': row['team'],
                        'total_score': row['total_score'],
                        'vorp_score': row['vorp_score'],
                        'tier': row['tier'],
                        'consistency_score': row.get('consistency_score', 0),
                        'ceiling_potential': row.get('ceiling_potential', 0)
                    }
                    for _, row in pos_df.iterrows()
                ]
            
            # Position scarcity analysis (now VORP-based)
            for position in df['position'].unique():
                pos_df = df[df['position'] == position]
                # Count players with significant VORP (top tier players)
                high_vorp_count = len(pos_df[pos_df['vorp_score'] > pos_df['vorp_score'].quantile(0.25)])
                medium_vorp_count = len(pos_df[(pos_df['vorp_score'] > pos_df['vorp_score'].quantile(0.5)) & 
                                             (pos_df['vorp_score'] <= pos_df['vorp_score'].quantile(0.25))])
                
                scarcity_level = 'high' if high_vorp_count <= 3 else 'medium' if high_vorp_count <= 6 else 'low'
                
                summary['position_scarcity'][position] = {
                    'high_vorp_count': high_vorp_count,
                    'medium_vorp_count': medium_vorp_count,
                    'scarcity_level': scarcity_level,
                    'draft_priority': 'early' if scarcity_level == 'high' else 'mid' if scarcity_level == 'medium' else 'late'
                }
            
            # Best values by VORP (highest VORP scores across all positions)
            best_values_df = df.nlargest(20, 'vorp_score')
            summary['best_values_by_vorp'] = [
                {
                    'player': row['player'],
                    'position': row['position'],
                    'team': row['team'],
                    'vorp_score': row['vorp_score'],
                    'total_score': row['total_score'],
                    'tier': row['tier']
                }
                for _, row in best_values_df.iterrows()
            ]
            
            # Risk/reward players (high ceiling, low consistency or injury risk)
            risk_reward_df = df[
                (df['ceiling_potential'] > 0.7) & 
                ((df['consistency_score'] < 0.6) | (df['injury_score'] < 0.8))
            ].head(10)
            
            summary['risk_reward_players'] = [
                {
                    'player': row['player'],
                    'position': row['position'],
                    'team': row['team'],
                    'vorp_score': row['vorp_score'],
                    'ceiling_potential': row['ceiling_potential'],
                    'consistency_score': row.get('consistency_score', 0),
                    'injury_score': row.get('injury_score', 1.0),
                    'risk_type': 'injury' if row.get('injury_score', 1.0) < 0.8 else 'inconsistency'
                }
                for _, row in risk_reward_df.iterrows()
            ]
            
            # Save summary
            summary_file = self.outputs_dir / "ranking_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Exported ranking summary to {summary_file}")
            
        except Exception as e:
            logger.error(f"Error creating ranking summary: {e}")
            raise
    
    def print_top_rankings(self, df: pd.DataFrame, position: str = None, top_n: int = 10) -> None:
        """Print top rankings in a nice format"""
        try:
            if position:
                pos_df = df[df['position'] == position].copy()
                print(f"\n🏈 Top {top_n} {position} Rankings (VORP-based):")
                print(f"📊 Total {position} players ranked: {len(pos_df)}")
            else:
                pos_df = df.copy()
                print(f"\n🏈 Top {top_n} Overall Rankings (VORP-based):")
                print(f"📊 Total players ranked: {len(pos_df)}")
            
            print("=" * 100)
            print(f"{'Rank':<4} {'Player':<20} {'Pos':<3} {'Team':<4} {'Score':<6} {'VORP':<6} {'Tier':<4} {'Age':<4} {'Exp':<4}")
            print("-" * 100)
            
            for _, row in pos_df.head(top_n).iterrows():
                print(f"{int(row['rank']):<4} {row['player']:<20} {row['position']:<3} "
                      f"{row['team']:<4} {row['total_score']:<6.1f} {row['vorp_score']:<6.1f} {int(row['tier']):<4} "
                      f"{row.get('age', 'N/A'):<4} {row.get('experience', 'N/A'):<4}")
            
            print("=" * 100)
            
        except Exception as e:
            logger.error(f"Error printing rankings: {e}")
    
    def print_vorp_analysis(self, df: pd.DataFrame) -> None:
        """Print VORP analysis for draft strategy"""
        try:
            print("\n📊 VORP Analysis for Draft Strategy:")
            print("=" * 80)
            print(f"{'Position':<8} {'Baseline':<10} {'Max VORP':<10} {'Avg VORP':<10} {'Above Baseline':<15}")
            print("-" * 80)
            
            for position in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']:
                pos_df = df[df['position'] == position]
                if len(pos_df) > 0:
                    baseline = pos_df['baseline_score'].iloc[0]
                    max_vorp = pos_df['vorp_score'].max()
                    avg_vorp = pos_df['vorp_score'].mean()
                    above_baseline = len(pos_df[pos_df['vorp_score'] > 0])
                    
                    print(f"{position:<8} {baseline:<10.1f} {max_vorp:<10.1f} {avg_vorp:<10.1f} {above_baseline:<15}")
            
            print("=" * 80)
            print("💡 Draft Strategy: Focus on positions with higher VORP scores")
            print("   - Higher VORP = More value over replacement level")
            print("   - Positions with steep VORP drops after top players are more scarce")
            
        except Exception as e:
            logger.error(f"Error printing VORP analysis: {e}")
    
    def print_best_values(self, df: pd.DataFrame, top_n: int = 15) -> None:
        """Print best value players by VORP score"""
        try:
            print(f"\n💎 Top {top_n} Value Picks (Highest VORP Scores):")
            print("=" * 100)
            print(f"{'Rank':<4} {'Player':<20} {'Pos':<3} {'Team':<4} {'VORP':<8} {'Score':<8} {'Tier':<4}")
            print("-" * 100)
            
            best_values = df.nlargest(top_n, 'vorp_score')
            for i, (_, row) in enumerate(best_values.iterrows(), 1):
                print(f"{i:<4} {row['player']:<20} {row['position']:<3} "
                      f"{row['team']:<4} {row['vorp_score']:<8.1f} {row['total_score']:<8.1f} {int(row['tier']):<4}")
            
            print("=" * 100)
            
        except Exception as e:
            logger.error(f"Error printing best values: {e}")

def main():
    """Main function to run the ranking system"""
    import argparse
    
    parser = argparse.ArgumentParser(description='NFL Fantasy Player Ranking System')
    parser.add_argument('--max-players', type=int, default=None, 
                       help='Maximum number of players to rank (default: None = all available)')
    parser.add_argument('--top-n', type=int, default=10, 
                       help='Number of top players to display per position (default: 10)')
    parser.add_argument('--position', type=str, choices=['QB', 'RB', 'WR', 'TE', 'ALL'], default='ALL',
                       help='Position to rank (default: ALL)')
    parser.add_argument('--rank-all', action='store_true',
                       help='Rank all available players (overrides max-players)')
    
    args = parser.parse_args()
    
    try:
        # If rank-all is specified, set max_players to None to rank all available
        max_players = None if args.rank_all else args.max_players
        
        # Initialize ranker
        ranker = PlayerRanker(max_players=max_players)
        
        # Generate rankings
        ranked_df = ranker.rank_players()
        
        # Export results
        ranker.export_rankings(ranked_df)
        
        # Print VORP analysis for draft strategy
        ranker.print_vorp_analysis(ranked_df)
        
        # Print best value picks by VORP (top 20 overall)
        ranker.print_best_values(ranked_df, top_n=20)
        
        # Print top rankings by position
        if args.position == 'ALL':
            print(f"\n🎯 TOP {args.top_n} PLAYERS BY POSITION (VORP-based)")
            print("=" * 80)
            
            for position in ['QB', 'RB', 'WR', 'TE']:
                ranker.print_top_rankings(ranked_df, position=position, top_n=args.top_n)
            
            # Print overall top players
            print(f"\n🏆 TOP {args.top_n} OVERALL PLAYERS (VORP-based)")
            ranker.print_top_rankings(ranked_df, top_n=args.top_n)
        else:
            ranker.print_top_rankings(ranked_df, position=args.position, top_n=args.top_n)
        
        # Print summary
        total_players = len(ranked_df)
        position_counts = ranked_df['position'].value_counts()
        print(f"\n📊 RANKING SUMMARY:")
        print(f"   Total players ranked: {total_players}")
        for pos, count in position_counts.items():
            print(f"   {pos}: {count} players")
        
        logger.info(f"Ranking process completed successfully! Ranked {total_players} players.")
        
    except Exception as e:
        logger.error(f"Error in main ranking process: {e}")
        raise

if __name__ == "__main__":
    main() 
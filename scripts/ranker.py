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
    
    def __init__(self, data_dir: str = "data", news_dir: str = "news", outputs_dir: str = "outputs"):
        self.data_dir = Path(data_dir)
        self.news_dir = Path(news_dir)
        self.outputs_dir = Path(outputs_dir)
        self.outputs_dir.mkdir(exist_ok=True)
        
        # Scoring weights (can be adjusted)
        self.weights = {
            'historical_performance': 0.35,  # Historical fantasy points
            'current_form': 0.25,            # Recent performance trend
            'injury_risk': -0.15,            # Injury proneness (negative)
            'experience_bonus': 0.10,        # Rookie/veteran considerations
            'team_context': 0.10,            # Team performance influence
            'news_sentiment': 0.10,          # Recent buzz and sentiment
            'consistency': 0.05              # Weekly performance stability
        }
        
        # Position-specific adjustments
        self.position_weights = {
            'QB': {'experience_bonus': 0.15, 'consistency': 0.10},  # QBs benefit from experience
            'RB': {'injury_risk': -0.20, 'current_form': 0.30},     # RBs more injury-prone, form matters more
            'WR': {'news_sentiment': 0.15, 'team_context': 0.15},   # WRs affected by team/QB changes
            'TE': {'experience_bonus': 0.05, 'consistency': 0.10},  # TEs benefit from consistency
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
            # Load enhanced player stats
            stats_file = self.data_dir / "enhanced_player_stats.csv"
            if not stats_file.exists():
                stats_file = self.data_dir / "base_player_stats.csv"
            
            stats_df = pd.read_csv(stats_file)
            logger.info(f"Loaded {len(stats_df)} players from stats file")
            
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
        """Calculate consistency score from weekly performance"""
        try:
            consistency = row.get('consistency_score', 0.5)
            weekly_std = row.get('weekly_std', 5.0)
            
            # Normalize consistency (higher is better)
            # Weekly std of 2 = very consistent, 10 = inconsistent
            std_score = max(0, 1.0 - (weekly_std - 2) / 8)
            
            # Combine consistency metrics
            final_consistency = (consistency * 0.7) + (std_score * 0.3)
            return final_consistency
            
        except Exception as e:
            logger.warning(f"Error calculating consistency for {row.get('player', 'Unknown')}: {e}")
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
                'consistency': self.calculate_consistency_score(row)
            }
            
            # Calculate weighted total
            total_score = sum(scores[component] * weights[component] for component in scores)
            
            # Normalize to 0-100 scale
            total_score = total_score * 100
            
            return total_score
            
        except Exception as e:
            logger.error(f"Error calculating total score for {row.get('player', 'Unknown')}: {e}")
            return 0.0
    
    def assign_tiers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Assign tiers based on score distribution"""
        try:
            # Group by position for tier assignment
            for position in df['position'].unique():
                pos_mask = df['position'] == position
                pos_scores = df.loc[pos_mask, 'total_score']
                
                if len(pos_scores) == 0:
                    continue
                
                # Calculate tier boundaries
                tier1_cutoff = pos_scores.quantile(0.1)  # Top 10%
                tier2_cutoff = pos_scores.quantile(0.25)  # Top 25%
                tier3_cutoff = pos_scores.quantile(0.5)   # Top 50%
                tier4_cutoff = pos_scores.quantile(0.75)  # Top 75%
                
                # Assign tiers
                df.loc[pos_mask, 'tier'] = 5  # Default tier
                df.loc[pos_mask & (pos_scores >= tier1_cutoff), 'tier'] = 1
                df.loc[pos_mask & (pos_scores < tier1_cutoff) & (pos_scores >= tier2_cutoff), 'tier'] = 2
                df.loc[pos_mask & (pos_scores < tier2_cutoff) & (pos_scores >= tier3_cutoff), 'tier'] = 3
                df.loc[pos_mask & (pos_scores < tier3_cutoff) & (pos_scores >= tier4_cutoff), 'tier'] = 4
            
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
            
            # Sort by total score within each position
            stats_df = stats_df.sort_values(['position', 'total_score'], ascending=[True, False])
            
            # Assign ranks within positions
            stats_df['rank'] = stats_df.groupby('position')['total_score'].rank(method='dense', ascending=False)
            
            # Assign tiers
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
            
            # Create summary JSON
            summary = {
                'total_players': len(df),
                'positions': df['position'].value_counts().to_dict(),
                'tiers': df['tier'].value_counts().to_dict(),
                'top_players_by_position': {},
                'ranked_at': datetime.now().isoformat()
            }
            
            for position in df['position'].unique():
                pos_df = df[df['position'] == position]
                top_5 = pos_df.head(5)[['player', 'team', 'total_score', 'tier']].to_dict('records')
                summary['top_players_by_position'][position] = top_5
            
            summary_file = self.outputs_dir / "ranking_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Exported ranking summary to {summary_file}")
            
        except Exception as e:
            logger.error(f"Error exporting rankings: {e}")
            raise
    
    def print_top_rankings(self, df: pd.DataFrame, position: str = None, top_n: int = 10) -> None:
        """Print top rankings in a nice format"""
        try:
            if position:
                df = df[df['position'] == position]
                print(f"\n🏈 Top {top_n} {position} Rankings:")
            else:
                print(f"\n🏈 Top {top_n} Overall Rankings:")
            
            print("=" * 80)
            print(f"{'Rank':<4} {'Player':<20} {'Pos':<3} {'Team':<4} {'Score':<6} {'Tier':<4} {'Age':<4} {'Exp':<4}")
            print("-" * 80)
            
            for _, row in df.head(top_n).iterrows():
                print(f"{int(row['rank']):<4} {row['player']:<20} {row['position']:<3} "
                      f"{row['team']:<4} {row['total_score']:<6.1f} {int(row['tier']):<4} "
                      f"{row.get('age', 'N/A'):<4} {row.get('experience', 'N/A'):<4}")
            
            print("=" * 80)
            
        except Exception as e:
            logger.error(f"Error printing rankings: {e}")

def main():
    """Main function to run the ranking system"""
    try:
        # Initialize ranker
        ranker = PlayerRanker()
        
        # Generate rankings
        ranked_df = ranker.rank_players()
        
        # Export results
        ranker.export_rankings(ranked_df)
        
        # Print top rankings by position
        for position in ['QB', 'RB', 'WR', 'TE']:
            ranker.print_top_rankings(ranked_df, position=position, top_n=10)
        
        # Print overall top 20
        ranker.print_top_rankings(ranked_df, top_n=20)
        
        logger.info("Ranking process completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main ranking process: {e}")
        raise

if __name__ == "__main__":
    main() 
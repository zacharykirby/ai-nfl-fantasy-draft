#!/usr/bin/env python3
"""
Fix NFL Fantasy Ranking System Issues
Implements critical fixes for Travis Kelce and other aging player ranking problems
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RankingSystemFixer:
    """Implements fixes for the ranking system issues"""
    
    def __init__(self, data_dir: str = "data", outputs_dir: str = "outputs"):
        self.data_dir = Path(data_dir)
        self.outputs_dir = Path(outputs_dir)
        self.outputs_dir.mkdir(exist_ok=True)
        
        # Position-specific age decline curves
        self.age_decline_curves = {
            'QB': {
                'start_age': 32,
                'gradual_decline': 0.03,  # 3% per year
                'steep_decline_age': 35,
                'steep_decline': 0.08,    # 8% per year
                'max_penalty': 0.40       # 40% max penalty
            },
            'RB': {
                'start_age': 28,
                'gradual_decline': 0.08,  # 8% per year
                'steep_decline_age': 30,
                'steep_decline': 0.15,    # 15% per year
                'max_penalty': 0.60       # 60% max penalty
            },
            'WR': {
                'start_age': 30,
                'gradual_decline': 0.05,  # 5% per year
                'steep_decline_age': 33,
                'steep_decline': 0.10,    # 10% per year
                'max_penalty': 0.50       # 50% max penalty
            },
            'TE': {
                'start_age': 30,
                'gradual_decline': 0.08,  # 8% per year
                'steep_decline_age': 32,
                'steep_decline': 0.12,    # 12% per year
                'max_penalty': 0.55       # 55% max penalty
            }
        }
    
    def calculate_enhanced_age_penalty(self, row: pd.Series) -> float:
        """
        Calculate enhanced age penalty based on position and age
        """
        try:
            age = row.get('age', 25)
            position = row.get('position', 'WR')
            
            if position not in self.age_decline_curves:
                return 0.0
            
            curve = self.age_decline_curves[position]
            
            if age < curve['start_age']:
                return 0.0
            
            # Calculate penalty based on age curve
            if age < curve['steep_decline_age']:
                # Gradual decline phase
                years_over_start = age - curve['start_age']
                penalty = years_over_start * curve['gradual_decline']
            else:
                # Steep decline phase
                years_gradual = curve['steep_decline_age'] - curve['start_age']
                years_steep = age - curve['steep_decline_age']
                penalty = (years_gradual * curve['gradual_decline'] + 
                          years_steep * curve['steep_decline'])
            
            # Cap at maximum penalty
            penalty = min(penalty, curve['max_penalty'])
            
            return penalty
            
        except Exception as e:
            logger.warning(f"Error calculating age penalty for {row.get('player', 'Unknown')}: {e}")
            return 0.0
    
    def detect_performance_decline(self, row: pd.Series, historical_data: pd.DataFrame) -> Dict:
        """
        Detect performance decline patterns
        """
        try:
            player_name = row.get('player', '')
            player_history = historical_data[historical_data['player'] == player_name]
            
            if len(player_history) < 2:
                return {'decline_detected': False, 'decline_severity': 0.0, 'consecutive_declines': 0}
            
            # Sort by season and get fantasy points
            player_history = player_history.sort_values('season')
            points = player_history['points_2024'].tolist()  # Using standardized column name
            
            if len(points) < 2:
                return {'decline_detected': False, 'decline_severity': 0.0, 'consecutive_declines': 0}
            
            # Calculate year-over-year changes
            declines = []
            consecutive_declines = 0
            max_consecutive = 0
            
            for i in range(1, len(points)):
                if points[i] < points[i-1]:
                    decline_pct = (points[i-1] - points[i]) / points[i-1]
                    declines.append(decline_pct)
                    consecutive_declines += 1
                    max_consecutive = max(max_consecutive, consecutive_declines)
                else:
                    consecutive_declines = 0
            
            if not declines:
                return {'decline_detected': False, 'decline_severity': 0.0, 'consecutive_declines': 0}
            
            # Calculate decline severity
            avg_decline = np.mean(declines)
            total_decline = sum(declines)
            
            # Determine severity tier
            if total_decline > 0.3 or avg_decline > 0.15:
                severity = 'severe'
                severity_score = 0.3
            elif total_decline > 0.2 or avg_decline > 0.10:
                severity = 'moderate'
                severity_score = 0.2
            else:
                severity = 'mild'
                severity_score = 0.1
            
            # Additional penalty for consecutive declines
            consecutive_penalty = min(max_consecutive * 0.05, 0.15)
            
            return {
                'decline_detected': True,
                'decline_severity': severity_score + consecutive_penalty,
                'consecutive_declines': max_consecutive,
                'avg_decline': avg_decline,
                'total_decline': total_decline,
                'severity_tier': severity
            }
            
        except Exception as e:
            logger.warning(f"Error detecting decline for {row.get('player', 'Unknown')}: {e}")
            return {'decline_detected': False, 'decline_severity': 0.0, 'consecutive_declines': 0}
    
    def apply_enhanced_penalties(self, df: pd.DataFrame, historical_data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply enhanced age and decline penalties to the dataset
        """
        try:
            logger.info("Applying enhanced age and decline penalties...")
            
            # Calculate age penalties
            df['age_penalty'] = df.apply(self.calculate_enhanced_age_penalty, axis=1)
            
            # Detect performance declines
            decline_results = []
            for _, row in df.iterrows():
                decline_info = self.detect_performance_decline(row, historical_data)
                decline_results.append(decline_info)
            
            # Add decline information to dataframe
            df['decline_detected'] = [r['decline_detected'] for r in decline_results]
            df['decline_severity'] = [r['decline_severity'] for r in decline_results]
            df['consecutive_declines'] = [r['consecutive_declines'] for r in decline_results]
            
            # Calculate total penalty
            df['total_age_decline_penalty'] = df['age_penalty'] + df['decline_severity']
            
            # Apply penalties to total score
            df['adjusted_total_score'] = df['total_score'] * (1 - df['total_age_decline_penalty'])
            
            # Log significant penalties
            significant_penalties = df[df['total_age_decline_penalty'] > 0.1]
            for _, row in significant_penalties.iterrows():
                logger.info(f"Applied {row['total_age_decline_penalty']:.2%} penalty to {row['player']} "
                          f"(age: {row['age']}, position: {row['position']})")
            
            return df
            
        except Exception as e:
            logger.error(f"Error applying enhanced penalties: {e}")
            return df
    
    def fix_data_priority_issues(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fix data priority issues by ensuring current season data is used
        """
        try:
            logger.info("Fixing data priority issues...")
            
            # Check for players with multiple season entries
            player_counts = df['player'].value_counts()
            duplicate_players = player_counts[player_counts > 1].index.tolist()
            
            if duplicate_players:
                logger.info(f"Found {len(duplicate_players)} players with multiple season entries")
                
                # For each duplicate player, keep the most recent season
                fixed_df = []
                for player in duplicate_players:
                    player_data = df[df['player'] == player]
                    
                    # Sort by season (assuming season is in the data)
                    if 'season' in player_data.columns:
                        player_data = player_data.sort_values('season', ascending=False)
                        # Keep the most recent season
                        fixed_df.append(player_data.iloc[0])
                    else:
                        # If no season column, keep the first entry but log it
                        logger.warning(f"No season data for {player}, keeping first entry")
                        fixed_df.append(player_data.iloc[0])
                
                # Add players without duplicates
                single_players = df[~df['player'].isin(duplicate_players)]
                fixed_df.extend([row for _, row in single_players.iterrows()])
                
                df = pd.DataFrame(fixed_df)
                logger.info(f"Fixed data priority: {len(df)} unique players")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fixing data priority issues: {e}")
            return df
    
    def generate_fixed_rankings(self) -> pd.DataFrame:
        """
        Generate rankings with all fixes applied
        """
        try:
            logger.info("Generating fixed rankings...")
            
            # Load current rankings
            rankings_file = self.outputs_dir / "ranked_all_players.csv"
            if not rankings_file.exists():
                logger.error("No rankings file found. Run ranker.py first.")
                return None
            
            df = pd.read_csv(rankings_file)
            
            # Load historical data for decline detection
            historical_file = self.data_dir / "nfl_player_data.csv"
            historical_data = pd.DataFrame()
            if historical_file.exists():
                historical_data = pd.read_csv(historical_file)
                logger.info(f"Loaded historical data: {len(historical_data)} records")
            
            # Apply fixes
            df = self.fix_data_priority_issues(df)
            df = self.apply_enhanced_penalties(df, historical_data)
            
            # Recalculate VORP scores with adjusted total scores
            df = self.recalculate_vorp_scores(df)
            
            # Sort by adjusted total score
            df = df.sort_values('adjusted_total_score', ascending=False)
            
            # Save fixed rankings
            output_file = self.outputs_dir / "ranked_all_players_fixed.csv"
            df.to_csv(output_file, index=False)
            logger.info(f"Saved fixed rankings to {output_file}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error generating fixed rankings: {e}")
            return None
    
    def recalculate_vorp_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Recalculate VORP scores using adjusted total scores
        """
        try:
            # Group by position and calculate baseline scores
            for position in df['position'].unique():
                pos_df = df[df['position'] == position]
                
                # Calculate 25th percentile as baseline
                baseline_score = pos_df['adjusted_total_score'].quantile(0.25)
                
                # Calculate VORP
                df.loc[df['position'] == position, 'adjusted_baseline_score'] = baseline_score
                df.loc[df['position'] == position, 'adjusted_vorp_score'] = (
                    df.loc[df['position'] == position, 'adjusted_total_score'] - baseline_score
                )
            
            return df
            
        except Exception as e:
            logger.error(f"Error recalculating VORP scores: {e}")
            return df
    
    def compare_rankings(self, original_file: str = "ranked_all_players.csv", 
                        fixed_file: str = "ranked_all_players_fixed.csv") -> None:
        """
        Compare original and fixed rankings
        """
        try:
            original_path = self.outputs_dir / original_file
            fixed_path = self.outputs_dir / fixed_file
            
            if not original_path.exists() or not fixed_path.exists():
                logger.error("Ranking files not found for comparison")
                return
            
            original_df = pd.read_csv(original_path)
            fixed_df = pd.read_csv(fixed_path)
            
            # Focus on Travis Kelce and other aging players
            test_players = ['Travis Kelce', 'George Kittle', 'Mark Andrews', 'T.J. Hockenson']
            
            print("\n" + "="*80)
            print("RANKING COMPARISON: ORIGINAL vs FIXED")
            print("="*80)
            
            for player in test_players:
                orig_row = original_df[original_df['player'] == player]
                fixed_row = fixed_df[fixed_df['player'] == player]
                
                if len(orig_row) > 0 and len(fixed_row) > 0:
                    orig_score = orig_row['total_score'].iloc[0]
                    fixed_score = fixed_row['adjusted_total_score'].iloc[0]
                    orig_rank = orig_row['rank'].iloc[0]
                    fixed_rank = fixed_row.index[0] + 1  # Position in sorted dataframe
                    
                    print(f"\n{player}:")
                    print(f"  Original: Rank {orig_rank}, Score {orig_score:.1f}")
                    print(f"  Fixed:    Rank {fixed_rank}, Score {fixed_score:.1f}")
                    print(f"  Change:   Rank {orig_rank - fixed_rank:+d}, Score {fixed_score - orig_score:+.1f}")
                    
                    if 'total_age_decline_penalty' in fixed_row.columns:
                        penalty = fixed_row['total_age_decline_penalty'].iloc[0]
                        print(f"  Age/Decline Penalty: {penalty:.1%}")
            
            print("\n" + "="*80)
            
        except Exception as e:
            logger.error(f"Error comparing rankings: {e}")

def main():
    """Main function to run the ranking system fixes"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix NFL Fantasy Ranking System Issues')
    parser.add_argument('--compare', action='store_true', 
                       help='Compare original and fixed rankings')
    parser.add_argument('--generate', action='store_true',
                       help='Generate fixed rankings')
    
    args = parser.parse_args()
    
    fixer = RankingSystemFixer()
    
    if args.generate:
        df = fixer.generate_fixed_rankings()
        if df is not None:
            print(f"\n✅ Successfully generated fixed rankings for {len(df)} players")
            
            # Show top 10 TEs with fixes
            te_df = df[df['position'] == 'TE'].head(10)
            print(f"\n🏈 Top 10 TEs (Fixed Rankings):")
            print("="*60)
            for i, (_, row) in enumerate(te_df.iterrows(), 1):
                penalty = row.get('total_age_decline_penalty', 0)
                print(f"{i:2d}. {row['player']:<20} {row['adjusted_total_score']:6.1f} "
                      f"(penalty: {penalty:.1%})")
    
    if args.compare:
        fixer.compare_rankings()
    
    if not args.generate and not args.compare:
        print("Use --generate to create fixed rankings or --compare to compare rankings")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Data Ingestion Module

This module fetches fantasy football data from nfl_data_py and processes it
into a standardized format for the ranking system.
"""

import pandas as pd
import nfl_data_py as nfl
import json
import time
from typing import Dict, List, Optional
import logging
from pathlib import Path
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FantasyDataIngester:
    """Handles fetching and processing fantasy football data from nfl_data_py."""
    
    def __init__(self):
        # Create data directory if it doesn't exist
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)

    def default_historical_years(self, lookback: int = 3) -> List[int]:
        """Return the most recent completed NFL seasons for historical analysis."""
        last_completed_season = datetime.now().year - 1
        return list(range(last_completed_season - lookback + 1, last_completed_season + 1))

    @staticmethod
    def _nflverse_player_stats_url(year: int, summary_level: str) -> str:
        """Return the maintained nflverse player-stats release URL."""
        return (
            "https://github.com/nflverse/nflverse-data/releases/download/"
            f"stats_player/stats_player_{summary_level}_{year}.csv"
        )

    def _get_nflverse_player_stats(self, year: int, summary_level: str) -> pd.DataFrame:
        """Fetch current nflverse stats when the archived nfl_data_py URLs fail."""
        url = self._nflverse_player_stats_url(year, summary_level)
        logger.info("Fetching %s player stats from nflverse release", summary_level, extra={"url": url})
        df = pd.read_csv(url, low_memory=False)

        # nflverse's current release uses clearer names than nfl_data_py. Normalize
        # only the fields whose names changed; the remaining stat columns already
        # match the historical schema used by the ranker.
        df = df.rename(
            columns={
                "passing_interceptions": "interceptions",
                "player_display_name": "display_name",
            }
        )
        if summary_level == "week":
            return df

        # Seasonal identity comes from the roster merge, just as it did with the
        # legacy provider. Avoid position_x/team_x columns during that merge.
        return df.drop(
            columns=["player_name", "display_name", "position", "position_group", "recent_team"],
            errors="ignore",
        )
        
    def get_seasonal_data(self, years: List[int] = [2023]) -> pd.DataFrame:
        """
        Fetch seasonal data from nfl_data_py.
        This provides comprehensive player statistics for the specified years.
        """
        logger.info(f"Fetching seasonal data for years: {years}")
        
        frames = []
        for year in years:
            try:
                df = nfl.import_seasonal_data(years=[year], s_type='REG')
                if not df.empty:
                    frames.append(df)
                    logger.info(f"Fetched {len(df)} seasonal records for {year}")
            except Exception as e:
                logger.warning(f"Legacy seasonal fetch failed for {year}: {e}")
                try:
                    df = self._get_nflverse_player_stats(year, "reg")
                    if not df.empty:
                        frames.append(df)
                        logger.info(f"Fetched {len(df)} seasonal records for {year} from nflverse")
                except Exception as fallback_error:
                    logger.warning(f"Skipping seasonal data for {year}: {fallback_error}")

        if not frames:
            logger.error("No seasonal data could be fetched")
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)
        df = self._clean_seasonal_data(df)

        logger.info(f"Successfully fetched {len(df)} player records from seasonal data")
        return df
    
    def get_weekly_data(self, years: List[int] = [2023]) -> pd.DataFrame:
        """
        Fetch weekly data from nfl_data_py.
        This provides per-game statistics for more detailed analysis.
        """
        logger.info(f"Fetching weekly data for years: {years}")
        
        frames = []
        for year in years:
            try:
                df = nfl.import_weekly_data(years=[year], downcast=True)
                if not df.empty:
                    frames.append(df)
                    logger.info(f"Fetched {len(df)} weekly records for {year}")
            except Exception as e:
                logger.warning(f"Legacy weekly fetch failed for {year}: {e}")
                try:
                    df = self._get_nflverse_player_stats(year, "week")
                    if not df.empty:
                        frames.append(df)
                        logger.info(f"Fetched {len(df)} weekly records for {year} from nflverse")
                except Exception as fallback_error:
                    logger.warning(f"Skipping weekly data for {year}: {fallback_error}")

        if not frames:
            logger.error("No weekly data could be fetched")
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)
        df = self._clean_weekly_data(df)

        logger.info(f"Successfully fetched {len(df)} weekly records")
        return df
    
    def get_roster_data(self, years: List[int] = [2023]) -> pd.DataFrame:
        """
        Fetch roster data from nfl_data_py.
        This provides player information like position, team, etc.
        """
        logger.info(f"Fetching roster data for years: {years}")
        
        frames = []
        for year in years:
            try:
                df = nfl.import_seasonal_rosters(years=[year])
                if not df.empty:
                    frames.append(df)
                    logger.info(f"Fetched {len(df)} roster records for {year}")
            except Exception as e:
                logger.warning(f"Skipping roster data for {year}: {e}")

        if not frames:
            logger.error("No roster data could be fetched")
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)
        df = self._clean_roster_data(df)

        logger.info(f"Successfully fetched {len(df)} roster records")
        return df
    
    def get_combine_data(self, years: List[int] = [2020, 2021, 2022, 2023, 2024]) -> pd.DataFrame:
        """
        Fetch combine data from nfl_data_py.
        This provides physical measurements and athletic testing data.
        """
        logger.info(f"Fetching combine data for years: {years}")
        
        try:
            # Get combine data for all positions
            positions = ['QB', 'RB', 'WR', 'TE']
            df = nfl.import_combine_data(years=years, positions=positions)
            
            # Clean up the data
            df = self._clean_combine_data(df)
            
            logger.info(f"Successfully fetched {len(df)} combine records")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching combine data: {e}")
            return pd.DataFrame()
    
    def _clean_seasonal_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize seasonal data.
        """
        if df.empty:
            return df
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['player_id', 'season'], keep='first')
        
        # Note: Seasonal data doesn't have position column, we'll get it from roster data
        # Filter for players with meaningful stats (at least some fantasy points)
        if 'fantasy_points_ppr' in df.columns:
            df = df[df['fantasy_points_ppr'] > 0]
        
        # Fill missing values
        numeric_columns = df.select_dtypes(include=['number']).columns
        for col in numeric_columns:
            df[col] = df[col].fillna(0)
        
        # Add derived features
        df = self._add_fantasy_features(df)
        
        return df
    
    def _clean_weekly_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize weekly data.
        """
        if df.empty:
            return df
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['player_id', 'season', 'week'], keep='first')
        
        # Note: Weekly data doesn't have position column, we'll get it from roster data
        # Filter for players with meaningful stats
        if 'fantasy_points_ppr' in df.columns:
            df = df[df['fantasy_points_ppr'] > 0]
        
        # Fill missing values
        numeric_columns = df.select_dtypes(include=['number']).columns
        for col in numeric_columns:
            df[col] = df[col].fillna(0)
        
        return df
    
    def _clean_roster_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize roster data.
        """
        if df.empty:
            return df
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['player_id', 'season'], keep='first')
        
        # Filter for fantasy-relevant positions
        fantasy_positions = ['QB', 'RB', 'WR', 'TE']
        df = df[df['position'].isin(fantasy_positions)]
        
        # Clean team names
        if 'team' in df.columns:
            df['team'] = df['team'].fillna('FA')
        
        return df
    
    def _clean_combine_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize combine data.
        """
        if df.empty:
            return df
        
        # Remove duplicates - combine data doesn't have player_id, use player_name
        df = df.drop_duplicates(subset=['player_name'], keep='first')
        
        # Filter for fantasy-relevant positions
        fantasy_positions = ['QB', 'RB', 'WR', 'TE']
        df = df[df['pos'].isin(fantasy_positions)]
        
        # Rename columns to match expected format
        column_mapping = {
            'pos': 'position',
            'ht': 'height',
            'wt': 'weight',
            'cone': 'three_cone'
        }
        df = df.rename(columns=column_mapping)
        
        # Fill missing values
        numeric_columns = df.select_dtypes(include=['number']).columns
        for col in numeric_columns:
            df[col] = df[col].fillna(0)
        
        return df
    
    def _add_fantasy_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add fantasy-relevant derived features.
        """
        # nfl_data_py already provides fantasy_points_ppr, so we'll use that
        if 'fantasy_points_ppr' in df.columns:
            df['total_fantasy_points'] = df['fantasy_points_ppr']
        
        # Calculate additional fantasy metrics if raw stats are available
        if 'receptions' in df.columns and 'receiving_yards' in df.columns and 'receiving_tds' in df.columns:
            df['receiving_fantasy_points'] = (
                df['receptions'] * 1.0 +  # PPR
                df['receiving_yards'] * 0.1 +
                df['receiving_tds'] * 6.0
            )
        
        if 'carries' in df.columns and 'rushing_yards' in df.columns and 'rushing_tds' in df.columns:
            df['rushing_fantasy_points'] = (
                df['rushing_yards'] * 0.1 +
                df['rushing_tds'] * 6.0
            )
        
        if 'completions' in df.columns and 'passing_yards' in df.columns and 'passing_tds' in df.columns and 'interceptions' in df.columns:
            df['passing_fantasy_points'] = (
                df['passing_yards'] * 0.04 +
                df['passing_tds'] * 4.0 -
                df['interceptions'] * 2.0
            )
        
        # Add experience level based on years_exp from roster data
        if 'years_exp' in df.columns:
            df['experience_level'] = df['years_exp'].apply(
                lambda x: 'Rookie' if pd.isna(x) or x == 0 else 
                         'Veteran' if x > 5 else 'Young'
            )
        else:
            df['experience_level'] = 'Unknown'
        
        # Add position tier (for scoring) - will be added when we merge with roster data
        if 'position' in df.columns:
            position_tiers = {
                'QB': 1, 'RB': 2, 'WR': 2, 'TE': 3
            }
            df['position_tier'] = df['position'].map(position_tiers)
        
        return df
    
    def merge_data_sources(self, seasonal_df: pd.DataFrame, weekly_df: pd.DataFrame, 
                          roster_df: pd.DataFrame, combine_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge data from different sources into a comprehensive dataset.
        """
        logger.info("Merging data from all sources...")
        
        # Start with seasonal data as base
        if seasonal_df.empty:
            logger.warning("No seasonal data available")
            return pd.DataFrame()
        
        merged_df = seasonal_df.copy()
        
        # Merge with roster data for additional player info (position, team, etc.)
        if not roster_df.empty:
            roster_cols = ['player_id', 'season', 'team', 'position', 'height', 'weight', 'age', 'player_name']
            available_cols = [col for col in roster_cols if col in roster_df.columns]
            
            if available_cols:
                merged_df = pd.merge(
                    merged_df,
                    roster_df[available_cols],
                    on=['player_id', 'season'],
                    how='left'
                )
        
        # Merge with combine data for athletic measurements
        if not combine_df.empty:
            # Combine data doesn't have player_id, so we'll merge on player_name
            combine_cols = ['player_name', 'height', 'weight', 'forty', 'bench', 'vertical', 'broad_jump', 'three_cone', 'shuttle']
            available_cols = [col for col in combine_cols if col in combine_df.columns]
            
            if available_cols and 'player_name' in merged_df.columns:
                merged_df = pd.merge(
                    merged_df,
                    combine_df[available_cols],
                    on='player_name',
                    how='left'
                )
        
        # Add weekly consistency metrics if weekly data is available
        if not weekly_df.empty:
            weekly_stats = self._calculate_weekly_consistency(weekly_df)
            if not weekly_stats.empty:
                merged_df = pd.merge(
                    merged_df,
                    weekly_stats,
                    on=['player_id', 'season'],
                    how='left'
                )
        
        # Final cleanup
        merged_df = self._final_cleanup(merged_df)
        
        logger.info(f"Final merged dataset contains {len(merged_df)} players")
        return merged_df
    
    def _calculate_weekly_consistency(self, weekly_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate consistency metrics from weekly data.
        """
        if weekly_df.empty:
            return pd.DataFrame()
        
        # Group by player and season to calculate consistency metrics
        if 'fantasy_points_ppr' in weekly_df.columns:
            consistency_metrics = weekly_df.groupby(['player_id', 'season']).agg({
                'fantasy_points_ppr': ['mean', 'std', 'min', 'max', 'count']
            }).reset_index()
            
            # Flatten column names
            consistency_metrics.columns = [
                'player_id', 'season', 'avg_fantasy_points', 'std_fantasy_points', 
                'min_fantasy_points', 'max_fantasy_points', 'games_played'
            ]
            
            # Calculate consistency score (lower std = more consistent)
            consistency_metrics['consistency_score'] = (
                consistency_metrics['avg_fantasy_points'] / 
                (consistency_metrics['std_fantasy_points'] + 1)  # Add 1 to avoid division by zero
            )
            
            return consistency_metrics
        else:
            return pd.DataFrame()
    
    def _final_cleanup(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Final cleanup of the merged dataset.
        """
        # Remove duplicates
        df = df.drop_duplicates(subset=['player_id', 'season'], keep='first')
        
        # Fill missing values
        numeric_columns = df.select_dtypes(include=['number']).columns
        for col in numeric_columns:
            df[col] = df[col].fillna(0)
        
        # Fill missing categorical values
        categorical_columns = ['team', 'position', 'player_name']
        for col in categorical_columns:
            if col in df.columns:
                df[col] = df[col].fillna('Unknown')
        
        return df
    
    def save_data(self, df: pd.DataFrame, filename: str = "nfl_player_data.csv"):
        """
        Save processed data to CSV file.
        """
        output_path = self.data_dir / filename
        df.to_csv(output_path, index=False)
        logger.info(f"Data saved to {output_path}")
        
        # Also save a summary
        summary_path = self.data_dir / "data_summary.json"
        summary = {
            'total_players': len(df),
            'seasons': sorted(df['season'].unique().tolist()) if 'season' in df.columns else [],
            'positions': df['position'].value_counts().to_dict() if 'position' in df.columns else {},
            'teams': df['team'].value_counts().to_dict() if 'team' in df.columns else {},
            'columns': list(df.columns),
            'last_updated': pd.Timestamp.now().isoformat()
        }
        
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Summary saved to {summary_path}")
    
    def get_fantasy_data(self, years: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Main function to get fantasy data from nfl_data_py.
        """
        if years is None:
            years = self.default_historical_years()

        logger.info("Starting fantasy data ingestion from nfl_data_py...")
        
        # Fetch data from all sources
        seasonal_df = self.get_seasonal_data(years)
        weekly_df = self.get_weekly_data(years)
        roster_df = self.get_roster_data(years)
        combine_df = self.get_combine_data()

        seasonal_years = set(pd.to_numeric(seasonal_df.get('season'), errors='coerce').dropna().astype(int))
        missing_years = sorted(set(years) - seasonal_years)
        if missing_years:
            raise RuntimeError(
                "Historical ingestion is incomplete; missing seasonal stats for: {}".format(
                    ", ".join(str(year) for year in missing_years)
                )
            )
        
        # Merge and clean data
        final_df = self.merge_data_sources(seasonal_df, weekly_df, roster_df, combine_df)
        
        # Save to file
        if not final_df.empty:
            self.save_data(final_df)
        
        return final_df

def main():
    """Main function to run the data ingestion process."""
    ingester = FantasyDataIngester()
    
    try:
        # Get data for the most recent completed seasons.
        df = ingester.get_fantasy_data()
        
        if not df.empty:
            print(f"\n✅ Successfully ingested {len(df)} players")
            print(f"📊 Data saved to: data/nfl_player_data.csv")
            print(f"📋 Summary saved to: data/data_summary.json")
            
            # Show sample data
            print(f"\n📈 Sample data (first 5 players):")
            display_cols = ['player_name', 'position', 'team', 'season', 'total_fantasy_points']
            available_cols = [col for col in display_cols if col in df.columns]
            if available_cols:
                print(df[available_cols].head())
            
            # Show position distribution
            if 'position' in df.columns:
                print(f"\n🏈 Position distribution:")
                print(df['position'].value_counts())
            
            # Show season distribution
            if 'season' in df.columns:
                print(f"\n📅 Season distribution:")
                print(df['season'].value_counts().sort_index())
            
        else:
            print("❌ No data was ingested. Check the logs for errors.")
            
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 

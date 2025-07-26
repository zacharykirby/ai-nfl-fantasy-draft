#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Command Line Interface
Phase 5: Beautiful CLI for accessing all fantasy football functions

This module provides a comprehensive command-line interface for:
- Data ingestion and processing
- News fetching and analysis
- Player ranking and recommendations
- Interactive filtering and viewing
"""

import argparse
import sys
import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime
import time

# Import our modules
from data_ingest import FantasyDataIngester
from news_fetcher import fetch_headlines, save_headlines
from news_analyzer import analyze_headlines
from ranker import PlayerRanker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Colors:
    """ANSI color codes for beautiful terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class FantasyCLI:
    """Main CLI class for the NFL Fantasy Draft Assistant"""
    
    def __init__(self):
        self.data_ingester = FantasyDataIngester()
        self.ranker = PlayerRanker()
        
    def print_banner(self):
        """Print the beautiful application banner"""
        banner = f"""
{Colors.HEADER}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🏈 NFL FANTASY DRAFT ASSISTANT 🏈                        ║
║                                                                              ║
║  Your AI-powered companion for data-driven fantasy football decisions       ║
║  Combines player stats, news sentiment, and advanced analytics              ║
╚══════════════════════════════════════════════════════════════════════════════╝
{Colors.ENDC}"""
        print(banner)
    
    def print_section_header(self, title: str):
        """Print a section header with consistent styling"""
        print(f"\n{Colors.OKBLUE}{Colors.BOLD}━━━ {title} ━━━{Colors.ENDC}")
    
    def print_success(self, message: str):
        """Print a success message"""
        print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")
    
    def print_warning(self, message: str):
        """Print a warning message"""
        print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")
    
    def print_error(self, message: str):
        """Print an error message"""
        print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")
    
    def print_info(self, message: str):
        """Print an info message"""
        print(f"{Colors.OKCYAN}ℹ️  {message}{Colors.ENDC}")
    
    def run_full_pipeline(self, years: List[int] = [2022, 2023, 2024], 
                         max_news_age: int = 24, force_refresh: bool = False):
        """Run the complete fantasy football analysis pipeline"""
        self.print_banner()
        self.print_section_header("RUNNING COMPLETE FANTASY FOOTBALL PIPELINE")
        
        start_time = time.time()
        
        try:
            # Step 1: Data Ingestion
            self.print_section_header("STEP 1: DATA INGESTION")
            self.print_info("Fetching player statistics and fantasy data...")
            
            if not force_refresh and Path("data/enhanced_player_stats.csv").exists():
                self.print_success("Using existing player data (use --force-refresh to update)")
            else:
                df = self.data_ingester.get_fantasy_data(years=years)
                if not df.empty:
                    self.print_success(f"Successfully processed {len(df)} players")
                else:
                    self.print_error("Failed to fetch player data")
                    return False
            
            # Step 2: News Fetching
            self.print_section_header("STEP 2: NEWS FETCHING")
            self.print_info("Fetching latest fantasy football news...")
            
            headlines = fetch_headlines(max_age_hours=max_news_age)
            if headlines:
                save_headlines(headlines)
                self.print_success(f"Fetched {len(headlines)} headlines from {len(set(h['source'] for h in headlines))} sources")
            else:
                self.print_warning("No recent headlines found")
            
            # Step 3: News Analysis
            self.print_section_header("STEP 3: NEWS ANALYSIS")
            self.print_info("Analyzing news sentiment and extracting player features...")
            
            if headlines:
                analyze_headlines()  # This will read from news/raw_headlines.json and write to news/player_features.json
                self.print_success("News analysis completed")
            else:
                self.print_warning("Skipping news analysis (no headlines)")
            
            # Step 4: Player Ranking
            self.print_section_header("STEP 4: PLAYER RANKING")
            self.print_info("Generating comprehensive player rankings...")
            
            ranked_df = self.ranker.rank_players()
            if not ranked_df.empty:
                self.ranker.export_rankings(ranked_df)
                self.print_success(f"Generated rankings for {len(ranked_df)} players")
            else:
                self.print_error("Failed to generate rankings")
                return False
            
            # Step 5: Display Results
            self.print_section_header("STEP 5: RESULTS SUMMARY")
            self.display_ranking_summary()
            
            elapsed_time = time.time() - start_time
            self.print_success(f"Pipeline completed in {elapsed_time:.2f} seconds!")
            
            return True
            
        except Exception as e:
            self.print_error(f"Pipeline failed: {str(e)}")
            logger.error(f"Pipeline error: {e}")
            return False
    
    def display_ranking_summary(self):
        """Display a beautiful summary of the rankings"""
        try:
            summary_file = Path("outputs/ranking_summary.json")
            if not summary_file.exists():
                self.print_warning("No ranking summary found")
                return
            
            with open(summary_file, 'r') as f:
                summary = json.load(f)
            
            print(f"\n{Colors.BOLD}📊 RANKING SUMMARY{Colors.ENDC}")
            print(f"{'─' * 50}")
            
            # Overall stats
            print(f"Total Players: {summary['total_players']}")
            print(f"Positions: {', '.join([f'{pos} ({count})' for pos, count in summary['positions'].items()])}")
            print(f"Tiers: {', '.join([f'Tier {tier} ({count})' for tier, count in summary['tiers'].items()])}")
            
            # Position scarcity analysis
            if 'position_scarcity' in summary:
                print(f"\n{Colors.BOLD}🎯 POSITION SCARCITY ANALYSIS{Colors.ENDC}")
                print(f"{'─' * 50}")
                
                for position, scarcity in summary['position_scarcity'].items():
                    scarcity_emoji = "🔴" if scarcity['scarcity_level'] == 'high' else "🟡" if scarcity['scarcity_level'] == 'medium' else "🟢"
                    priority_emoji = "⚡" if scarcity['draft_priority'] == 'early' else "⏰" if scarcity['draft_priority'] == 'mid' else "⏳"
                    
                    print(f"{scarcity_emoji} {position}: {scarcity['tier1_count']} Tier 1, {scarcity['tier2_count']} Tier 2 - {priority_emoji} Draft {scarcity['draft_priority']}")
            
            # Top players by position
            print(f"\n{Colors.BOLD}🏆 TOP PLAYERS BY POSITION{Colors.ENDC}")
            print(f"{'─' * 50}")
            
            for position, players in summary['top_players_by_position'].items():
                print(f"\n{Colors.OKBLUE}{Colors.BOLD}{position}:{Colors.ENDC}")
                for i, player in enumerate(players[:3], 1):
                    tier_emoji = "🥇" if player['tier'] == 1.0 else "🥈" if player['tier'] == 2.0 else "🥉"
                    ceiling_emoji = "🚀" if player.get('ceiling_potential', 0) > 0.7 else "📈" if player.get('ceiling_potential', 0) > 0.5 else ""
                    consistency_emoji = "🎯" if player.get('consistency_score', 0) > 0.7 else "📊" if player.get('consistency_score', 0) > 0.5 else ""
                    
                    print(f"  {i}. {tier_emoji} {player['player']} ({player['team']}) - Score: {player['total_score']:.1f} {ceiling_emoji}{consistency_emoji}")
            
            # Risk/reward players
            if 'risk_reward_players' in summary and summary['risk_reward_players']:
                print(f"\n{Colors.BOLD}🧨 HIGH UPSIDE, HIGH RISK PLAYERS{Colors.ENDC}")
                print(f"{'─' * 50}")
                
                for player in summary['risk_reward_players'][:5]:
                    risk_emoji = "🚨" if player['risk_type'] == 'injury' else "📊"
                    ceiling_emoji = "🚀" if player['ceiling_potential'] > 0.8 else "📈"
                    
                    print(f"  {risk_emoji} {player['player']} ({player['position']}, {player['team']}) - Ceiling: {player['ceiling_potential']:.2f} {ceiling_emoji}")
                    print(f"     Risk: {player['risk_type']} - Consistency: {player['consistency_score']:.2f}")
            
        except Exception as e:
            self.print_error(f"Error displaying summary: {e}")
    
    def show_rankings(self, position: Optional[str] = None, top_n: int = 10, 
                     exclude_injured: bool = False, sort_by: str = "score"):
        """Display player rankings in a beautiful table format"""
        self.print_section_header("PLAYER RANKINGS")
        
        try:
            # Load the appropriate CSV file
            if position:
                csv_file = f"outputs/ranked_{position.upper()}.csv"
            else:
                csv_file = "outputs/ranked_all_players.csv"
            
            if not Path(csv_file).exists():
                self.print_error(f"Ranking file not found: {csv_file}")
                self.print_info("Run the pipeline first with: python scripts/cli.py --pipeline")
                return
            
            df = pd.read_csv(csv_file)
            
            # Apply filters
            if exclude_injured:
                if 'injury_flag' in df.columns:
                    df = df[df['injury_flag'] != True]
                    self.print_info(f"Excluding injured players...")
                elif 'injury_status' in df.columns:
                    df = df[df['injury_status'] == 'ACTIVE']
                    self.print_info(f"Excluding injured players...")
                else:
                    self.print_warning("Injury status not available, showing all players")
            
            # Sort by specified column
            if sort_by == "score":
                df = df.sort_values('total_score', ascending=False)
            elif sort_by == "buzz":
                if 'news_buzz_score' in df.columns:
                    df = df.sort_values('news_buzz_score', ascending=False)
                else:
                    self.print_warning("News buzz scores not available. Sorting by total score instead.")
                    df = df.sort_values('total_score', ascending=False)
            elif sort_by == "consistency":
                df = df.sort_values('consistency_score', ascending=False)
            
            # Limit to top N
            df = df.head(top_n)
            
            if df.empty:
                self.print_warning("No players found matching criteria")
                return
            
            # Display the table
            position_title = f" {position.upper()}" if position else ""
            print(f"\n{Colors.BOLD}🏈 TOP {top_n}{position_title} PLAYERS{Colors.ENDC}")
            print(f"{'─' * 100}")
            
            # Table header
            header = f"{'Rank':<4} {'Player':<20} {'Team':<4} {'Pos':<3} {'Score':<8} {'Tier':<5} {'Buzz':<6} {'Inj':<3}"
            print(f"{Colors.OKBLUE}{Colors.BOLD}{header}{Colors.ENDC}")
            print(f"{'─' * 100}")
            
            # Table rows
            for i, (_, row) in enumerate(df.iterrows(), 1):
                tier_emoji = "🥇" if row['tier'] == 1.0 else "🥈" if row['tier'] == 2.0 else "🥉" if row['tier'] == 3.0 else "📊"
                injury_icon = "🚨" if row.get('injury_flag', False) else "✅"
                
                line = (f"{i:<4} {row['player']:<20} {row['team']:<4} {row['position']:<3} "
                       f"{row['total_score']:<8.1f} {tier_emoji:<5} {row.get('news_buzz_score', 0):<6.1f} {injury_icon:<3}")
                print(line)
            
            print(f"{'─' * 100}")
            
        except Exception as e:
            self.print_error(f"Error displaying rankings: {e}")
    
    def show_player_details(self, player_name: str):
        """Show detailed information about a specific player"""
        self.print_section_header(f"PLAYER DETAILS: {player_name.upper()}")
        
        try:
            # Load all data sources
            stats_file = Path("data/enhanced_player_stats.csv")
            news_file = Path("news/player_features.json")
            ranking_file = Path("outputs/ranked_all_players.csv")
            
            if not stats_file.exists():
                self.print_error("Player stats not found. Run data ingestion first.")
                return
            
            # Load data
            stats_df = pd.read_csv(stats_file)
            player_stats = stats_df[stats_df['player'].str.contains(player_name, case=False, na=False)]
            
            if player_stats.empty:
                self.print_error(f"Player '{player_name}' not found")
                return
            
            player_stats = player_stats.iloc[0]
            
            # Display basic info
            print(f"\n{Colors.BOLD}📋 BASIC INFORMATION{Colors.ENDC}")
            print(f"{'─' * 40}")
            print(f"Name: {player_stats['player']}")
            print(f"Position: {player_stats['position']}")
            print(f"Team: {player_stats['team']}")
            print(f"Experience: {player_stats.get('experience_level', 'Unknown')}")
            
            # Display fantasy stats
            print(f"\n{Colors.BOLD}📊 FANTASY STATISTICS{Colors.ENDC}")
            print(f"{'─' * 40}")
            if 'fantasy_points_2023' in player_stats:
                print(f"2023 Fantasy Points: {player_stats['fantasy_points_2023']:.1f}")
            if 'fantasy_points_2022' in player_stats:
                print(f"2022 Fantasy Points: {player_stats['fantasy_points_2022']:.1f}")
            if 'consistency_score' in player_stats:
                print(f"Consistency Score: {player_stats['consistency_score']:.2f}")
            
            # Display news analysis
            if news_file.exists():
                with open(news_file, 'r') as f:
                    news_data = json.load(f)
                
                player_features = news_data.get('player_features', {}).get(player_stats['player'])
                if player_features:
                    print(f"\n{Colors.BOLD}📰 NEWS ANALYSIS{Colors.ENDC}")
                    print(f"{'─' * 40}")
                    print(f"Sentiment Score: {player_features.get('sentiment_score', 0):.2f}")
                    print(f"Buzz Score: {player_features.get('buzz_score', 0):.2f}")
                    print(f"Injury Flag: {'Yes' if player_features.get('injury_flag', False) else 'No'}")
                    
                    topics = player_features.get('topics', [])
                    if topics:
                        print(f"Topics: {', '.join(topics)}")
            
            # Display ranking info
            if ranking_file.exists():
                ranking_df = pd.read_csv(ranking_file)
                player_rank = ranking_df[ranking_df['player'].str.contains(player_name, case=False, na=False)]
                
                if not player_rank.empty:
                    player_rank = player_rank.iloc[0]
                    print(f"\n{Colors.BOLD}🏆 RANKING INFORMATION{Colors.ENDC}")
                    print(f"{'─' * 40}")
                    print(f"Total Score: {player_rank['total_score']:.2f}")
                    print(f"Tier: {player_rank['tier']}")
                    
                    # Find position rank
                    pos_rank = ranking_df[ranking_df['position'] == player_stats['position']]
                    pos_rank = pos_rank.sort_values('total_score', ascending=False)
                    player_pos_rank = pos_rank[pos_rank['player'].str.contains(player_name, case=False, na=False)]
                    if not player_pos_rank.empty:
                        actual_rank = pos_rank.index.get_loc(player_pos_rank.index[0]) + 1
                        print(f"Position Rank: #{actual_rank}")
            
        except Exception as e:
            self.print_error(f"Error showing player details: {e}")
    
    def run_data_ingestion(self, years: List[int] = [2022, 2023, 2024]):
        """Run only the data ingestion step"""
        self.print_section_header("DATA INGESTION")
        self.print_info("Fetching and processing player statistics...")
        
        try:
            df = self.data_ingester.get_fantasy_data(years=years)
            if not df.empty:
                self.print_success(f"Successfully processed {len(df)} players")
                return True
            else:
                self.print_error("Failed to fetch player data")
                return False
        except Exception as e:
            self.print_error(f"Data ingestion failed: {e}")
            return False
    
    def run_news_pipeline(self, max_age_hours: int = 24):
        """Run only the news fetching and analysis pipeline"""
        self.print_section_header("NEWS PIPELINE")
        
        try:
            # Fetch news
            self.print_info("Fetching latest fantasy football news...")
            headlines = fetch_headlines(max_age_hours=max_age_hours)
            if headlines:
                save_headlines(headlines)
                self.print_success(f"Fetched {len(headlines)} headlines")
                
                # Analyze news
                self.print_info("Analyzing news sentiment...")
                analyze_headlines()  # This will read from news/raw_headlines.json and write to news/player_features.json
                self.print_success("News analysis completed")
                return True
            else:
                self.print_warning("No recent headlines found")
                return False
        except Exception as e:
            self.print_error(f"News pipeline failed: {e}")
            return False
    
    def run_ranking(self):
        """Run only the player ranking step"""
        self.print_section_header("PLAYER RANKING")
        self.print_info("Generating player rankings...")
        
        try:
            ranked_df = self.ranker.rank_players()
            if not ranked_df.empty:
                self.ranker.export_rankings(ranked_df)
                self.print_success(f"Generated rankings for {len(ranked_df)} players")
                return True
            else:
                self.print_error("Failed to generate rankings")
                return False
        except Exception as e:
            self.print_error(f"Ranking failed: {e}")
            return False

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="🏈 NFL Fantasy Draft Assistant - AI-powered fantasy football analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/cli.py --pipeline                    # Run complete analysis
  python scripts/cli.py --rankings --position WR      # Show top WR rankings
  python scripts/cli.py --player "Patrick Mahomes"    # Show player details
  python scripts/cli.py --data-only                   # Only fetch player data
  python scripts/cli.py --news-only                   # Only fetch and analyze news
        """
    )
    
    # Main action groups
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--pipeline', action='store_true',
                             help='Run the complete fantasy football analysis pipeline')
    action_group.add_argument('--rankings', action='store_true',
                             help='Display player rankings')
    action_group.add_argument('--player', type=str, metavar='NAME',
                             help='Show detailed information about a specific player')
    action_group.add_argument('--data-only', action='store_true',
                             help='Run only data ingestion')
    action_group.add_argument('--news-only', action='store_true',
                             help='Run only news fetching and analysis')
    action_group.add_argument('--rank-only', action='store_true',
                             help='Run only player ranking (requires existing data)')
    
    # Filtering options
    parser.add_argument('--position', type=str, choices=['QB', 'RB', 'WR', 'TE', 'K', 'DST'],
                       help='Filter by position (for rankings)')
    parser.add_argument('--top', type=int, default=10, metavar='N',
                       help='Show top N players (default: 10)')
    parser.add_argument('--exclude-injured', action='store_true',
                       help='Exclude injured players from rankings')
    parser.add_argument('--sort-by', type=str, choices=['score', 'buzz', 'consistency'], default='score',
                       help='Sort rankings by (default: score)')
    
    # Pipeline options
    parser.add_argument('--years', type=int, nargs='+', default=[2022, 2023, 2024],
                       help='Years of data to analyze (default: 2022 2023 2024)')
    parser.add_argument('--news-age', type=int, default=24, metavar='HOURS',
                       help='Maximum age of news headlines in hours (default: 24)')
    parser.add_argument('--force-refresh', action='store_true',
                       help='Force refresh of existing data')
    
    args = parser.parse_args()
    
    # Initialize CLI
    cli = FantasyCLI()
    
    try:
        if args.pipeline:
            success = cli.run_full_pipeline(
                years=args.years,
                max_news_age=args.news_age,
                force_refresh=args.force_refresh
            )
            sys.exit(0 if success else 1)
            
        elif args.rankings:
            cli.show_rankings(
                position=args.position,
                top_n=args.top,
                exclude_injured=args.exclude_injured,
                sort_by=args.sort_by
            )
            
        elif args.player:
            cli.show_player_details(args.player)
            
        elif args.data_only:
            success = cli.run_data_ingestion(years=args.years)
            sys.exit(0 if success else 1)
            
        elif args.news_only:
            success = cli.run_news_pipeline(max_age_hours=args.news_age)
            sys.exit(0 if success else 1)
            
        elif args.rank_only:
            success = cli.run_ranking()
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Operation cancelled by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}Unexpected error: {e}{Colors.ENDC}")
        logger.error(f"CLI error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
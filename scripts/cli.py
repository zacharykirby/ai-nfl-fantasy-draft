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
from draft_recommender import DraftRecommender
from llm_client import OpenRouterClient
from draft_board import DraftBoardBuilder, LeagueConfig, format_board, load_board, validate_board
from fetch_2026_projections import build_projection_file, write_projection_artifacts
from projection_validator import validate_projection_file

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
        self.draft_recommender = None  # Initialize lazily to avoid connection issues
        
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

    def build_draft_board(self, top_n: int = None, league_size: int = 10, scoring: str = "half_ppr"):
        """Export the position-first JSON contract used by live draft clients."""
        self.print_section_header("BUILDING POSITION PRIORITY BOARD")
        try:
            limits = None
            if top_n is not None:
                limits = {position: top_n for position in ("QB", "RB", "WR", "TE")}
            builder = DraftBoardBuilder()
            board = builder.build(
                league=LeagueConfig(scoring=scoring, league_size=league_size),
                limits=limits,
            )
            output = builder.write(board)
            counts = board["metadata"]["role_counts"]
            self.print_success(
                "Exported {}".format(
                    ", ".join("{} {}".format(count, position) for position, count in counts.items())
                )
            )
            health = board["health"]
            if health["status"] == "ready":
                self.print_success("Board health: READY")
            else:
                self.print_warning(
                    "Board health: NOT READY ({} errors, {} warnings)".format(
                        health["error_count"], health["warning_count"]
                    )
                )
                for issue in health["issues"]:
                    print("- [{}] {}".format(issue["code"], issue["message"]))
            self.print_success("Saved board to {}".format(output))
            return True
        except Exception as exc:
            self.print_error("Board build failed: {}".format(exc))
            return False

    def validate_draft_board(self):
        """Validate the exported board and return false when it is unsafe for live advice."""
        self.print_section_header("DRAFT BOARD HEALTH")
        try:
            board = load_board()
            report = validate_board(board)
            print("Status: {}".format(report["status"].upper()))
            print("Errors: {} | Warnings: {}".format(report["error_count"], report["warning_count"]))
            for issue in report["issues"]:
                print("- {} [{}]: {}".format(issue["severity"].upper(), issue["code"], issue["message"]))
            return report["status"] == "ready"
        except Exception as exc:
            self.print_error("Board validation failed: {}".format(exc))
            return False

    def show_draft_board(self, position: str = None, top_n: int = 10):
        """Print role priorities from the stable board JSON."""
        self.print_section_header("PLAYER PRIORITIES BY ROLE")
        try:
            board = load_board()
            print(format_board(board, top_n=top_n, position=position))
            health = board.get("health", {})
            if health.get("status") != "ready":
                self.print_warning("This board is marked NOT READY; inspect --validate-board before using it live.")
            return True
        except Exception as exc:
            self.print_error("Unable to show board: {}".format(exc))
            return False

    def fetch_projections(self, season: int):
        """Fetch projections with a provenance manifest and report data health."""
        self.print_section_header("FETCHING PROJECTIONS AND ADP")
        try:
            output = build_projection_file()
            csv_path, metadata_path = write_projection_artifacts(output, season)
            self.print_success("Wrote {} players to {}".format(len(output), csv_path))
            self.print_success("Wrote source manifest to {}".format(metadata_path))
            return self.validate_projections(season)
        except Exception as exc:
            self.print_error("Projection fetch failed: {}".format(exc))
            return False

    def validate_projections(self, season: int):
        """Show projection provenance, coverage, and identity health."""
        self.print_section_header("PROJECTION DATA HEALTH")
        path = Path("data") / "players_{}_positions_bye.csv".format(season)
        report = validate_projection_file(path, expected_season=season)
        print("Status: {}".format(report["status"].upper()))
        print("Errors: {} | Warnings: {}".format(report["error_count"], report["warning_count"]))
        metrics = report.get("metrics", {})
        if metrics.get("position_counts"):
            print("Coverage: {}".format(
                ", ".join("{} {}".format(count, position) for position, count in metrics["position_counts"].items())
            ))
        if "estimated_projection_rate" in metrics:
            print("Estimated projections: {:.1%}".format(metrics["estimated_projection_rate"]))
        for issue in report["issues"]:
            print("- {} [{}]: {}".format(issue["severity"].upper(), issue["code"], issue["message"]))
        return report["status"] == "ready"
    
    def _load_rankings_dataframe(self) -> pd.DataFrame:
        """Load current JSON rankings and normalize legacy display column names."""
        ranking_file = Path("outputs/player_rankings.json")
        if not ranking_file.exists():
            raise FileNotFoundError(f"Ranking file not found: {ranking_file}")

        with open(ranking_file, "r") as f:
            payload = json.load(f)

        rankings = payload.get("rankings", payload) if isinstance(payload, dict) else payload
        if not isinstance(rankings, list):
            raise ValueError("Ranking file must contain a list or a rankings payload")

        df = pd.DataFrame(rankings)
        column_mapping = {
            "name": "player",
            "pos": "position",
            "score": "total_score",
            "VORP": "vorp_score",
        }
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df = df.rename(columns={old_col: new_col})

        for col, default in {
            "player": "Unknown",
            "position": "Unknown",
            "team": "Unknown",
            "total_score": 0.0,
            "vorp_score": 0.0,
            "tier": "Tier 5",
            "age": "N/A",
            "experience": "N/A",
            "consistency_score": 0.0,
            "baseline_score": 0.0,
        }.items():
            if col not in df.columns:
                df[col] = default

        for col in ["total_score", "vorp_score", "consistency_score", "baseline_score"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        return df

    def run_full_pipeline(self, years: Optional[List[int]] = None, 
                         max_news_age: int = 24, force_refresh: bool = False, skip_news: bool = False):
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
            
            # Step 2: News Fetching (skip if requested)
            if skip_news:
                self.print_section_header("STEP 2: NEWS FETCHING")
                self.print_info("Skipping news fetching (--skip-news flag used)")
                headlines = None
            else:
                self.print_section_header("STEP 2: NEWS FETCHING")
                self.print_info("Fetching latest fantasy football news...")
                
                headlines = fetch_headlines(max_age_hours=max_news_age)
                if headlines:
                    save_headlines(headlines)
                    self.print_success(f"Fetched {len(headlines)} headlines from {len(set(h['source'] for h in headlines))} sources")
                else:
                    self.print_warning("No recent headlines found")
            
            # Step 3: News Analysis (skip if no headlines or requested)
            if skip_news or not headlines:
                self.print_section_header("STEP 3: NEWS ANALYSIS")
                if skip_news:
                    self.print_info("Skipping news analysis (--skip-news flag used)")
                else:
                    self.print_warning("Skipping news analysis (no headlines)")
            else:
                self.print_section_header("STEP 3: NEWS ANALYSIS")
                self.print_info("Analyzing news sentiment and extracting player features...")
                analyze_headlines()  # This will read from news/raw_headlines.json and write to news/player_features.json
                self.print_success("News analysis completed")
            
            # Step 4: Player Ranking
            self.print_section_header("STEP 4: PLAYER RANKING")
            self.print_info("Generating comprehensive player rankings with VORP analysis...")
            
            ranked_df = self.ranker.rank_players()
            if not ranked_df.empty:
                self.ranker.export_rankings(ranked_df)
                self.print_success(f"Generated rankings for {len(ranked_df)} players")
                
                # Display VORP analysis
                self.print_section_header("VORP ANALYSIS")
                self.ranker.print_vorp_analysis(ranked_df)
                
                # Display best value picks
                self.print_section_header("BEST VALUE PICKS")
                # Note: print_best_values method not implemented yet
                
                # Display top players by position
                self.print_section_header("TOP PLAYERS BY POSITION")
                for position in ['QB', 'RB', 'WR', 'TE']:
                    self.ranker.print_top_rankings(ranked_df, position=position, top_n=7)
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
        """Display a beautiful summary of the rankings with VORP analysis"""
        try:
            summary_file = Path("outputs/ranking_summary.json")
            if not summary_file.exists():
                self.print_warning("No ranking summary found")
                return
            
            with open(summary_file, 'r') as f:
                summary = json.load(f)
            
            print(f"\n{Colors.BOLD}📊 RANKING SUMMARY{Colors.ENDC}")
            print(f"{'─' * 60}")
            
            # Overall stats
            print(f"Total Players: {summary['total_players']}")
            print(f"Positions: {', '.join([f'{pos} ({count})' for pos, count in summary['positions'].items()])}")
            print(f"Tiers: {', '.join([f'Tier {tier} ({count})' for tier, count in summary['tiers'].items()])}")
            
            # VORP Analysis
            if 'vorp_analysis' in summary:
                print(f"\n{Colors.BOLD}📈 VORP ANALYSIS{Colors.ENDC}")
                print(f"{'─' * 60}")
                print(f"{'Position':<8} {'Baseline':<10} {'Max VORP':<10} {'Avg VORP':<10} {'Above Baseline':<15}")
                print(f"{'─' * 60}")
                
                for position in ['QB', 'RB', 'WR', 'TE']:
                    if position in summary['vorp_analysis']:
                        vorp_data = summary['vorp_analysis'][position]
                        print(f"{position:<8} {vorp_data['baseline_score']:<10.1f} {vorp_data['max_vorp']:<10.1f} "
                              f"{vorp_data['avg_vorp']:<10.1f} {vorp_data['players_above_baseline']:<15}")
            
            # Position scarcity analysis
            if 'position_scarcity' in summary:
                print(f"\n{Colors.BOLD}🎯 POSITION SCARCITY ANALYSIS{Colors.ENDC}")
                print(f"{'─' * 60}")
                
                for position, scarcity in summary['position_scarcity'].items():
                    scarcity_emoji = "🔴" if scarcity['scarcity_level'] == 'high' else "🟡" if scarcity['scarcity_level'] == 'medium' else "🟢"
                    priority_emoji = "⚡" if scarcity['draft_priority'] == 'early' else "⏰" if scarcity['draft_priority'] == 'mid' else "⏳"
                    
                    print(f"{scarcity_emoji} {position}: {scarcity['above_zero']} Above Baseline VORP - {priority_emoji} Draft {scarcity['draft_priority']}")
            
            # Best values by VORP
            if 'best_values_by_vorp' in summary:
                print(f"\n{Colors.BOLD}💎 TOP VALUE PICKS (Highest VORP){Colors.ENDC}")
                print(f"{'─' * 60}")
                
                for i, player in enumerate(summary['best_values_by_vorp'][:20], 1):
                    tier_emoji = "🥇" if player['tier'] == 1 else "🥈" if player['tier'] == 2 else "🥉"
                    print(f"  {i}. {tier_emoji} {player['player']} ({player['position']}, {player['team']}) - VORP: {player['vorp_score']:.1f}")
            
            # Top players by position
            print(f"\n{Colors.BOLD}🏆 TOP PLAYERS BY POSITION{Colors.ENDC}")
            print(f"{'─' * 60}")
            
            for position, players in summary['top_players_by_position'].items():
                print(f"\n{Colors.OKBLUE}{Colors.BOLD}{position}:{Colors.ENDC}")
                for i, player in enumerate(players[:7], 1):
                    tier_emoji = "🥇" if player['tier'] == 1 else "🥈" if player['tier'] == 2 else "🥉"
                    vorp_emoji = "💎" if player.get('vorp_score', 0) > 10 else "📈" if player.get('vorp_score', 0) > 5 else ""
                    
                    print(f"  {i}. {tier_emoji} {player['player']} ({player['team']}) - Score: {player['total_score']:.1f}, VORP: {player.get('vorp_score', 0):.1f} {vorp_emoji}")
            
            # Risk/reward players
            if 'risk_reward_players' in summary and summary['risk_reward_players']:
                print(f"\n{Colors.BOLD}🧨 HIGH UPSIDE, HIGH RISK PLAYERS{Colors.ENDC}")
                print(f"{'─' * 60}")
                
                for player in summary['risk_reward_players'][:5]:
                    risk_emoji = "🚨" if player['risk_type'] == 'injury' else "📊"
                    ceiling_emoji = "🚀" if player['ceiling_potential'] > 0.8 else "📈"
                    
                    print(f"  {risk_emoji} {player['player']} ({player['position']}, {player['team']}) - VORP: {player['vorp_score']:.1f} {ceiling_emoji}")
                    print(f"     Risk: {player['risk_type']} - Consistency: {player['consistency_score']:.2f}")
            
        except Exception as e:
            self.print_error(f"Error displaying summary: {e}")
    
    def show_rankings(self, position: Optional[str] = None, top_n: int = 10, 
                     exclude_injured: bool = False, sort_by: str = "vorp"):
        """Display player rankings in a beautiful table format with VORP analysis"""
        self.print_section_header("PLAYER RANKINGS")
        
        try:
            df = self._load_rankings_dataframe()
            if position:
                df = df[df["position"] == position.upper()]
            
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
            
            # Sort by specified column (default to VORP for better draft strategy)
            if sort_by == "vorp":
                df = df.sort_values('vorp_score', ascending=False)
            elif sort_by == "score":
                df = df.sort_values('total_score', ascending=False)
            elif sort_by == "buzz":
                if 'news_buzz_score' in df.columns:
                    df = df.sort_values('news_buzz_score', ascending=False)
                else:
                    self.print_warning("News buzz scores not available. Sorting by VORP instead.")
                    df = df.sort_values('vorp_score', ascending=False)
            elif sort_by == "consistency":
                df = df.sort_values('consistency_score', ascending=False)
            
            # Limit to top N
            df = df.head(top_n)
            
            if df.empty:
                self.print_warning("No players found matching criteria")
                return
            
            # Display the table
            position_title = f" {position.upper()}" if position else ""
            print(f"\n{Colors.BOLD}🏈 TOP {top_n}{position_title} PLAYERS (VORP-based){Colors.ENDC}")
            print(f"{'─' * 120}")
            
            # Enhanced table header with VORP
            header = f"{'Rank':<4} {'Player':<20} {'Team':<4} {'Pos':<3} {'Score':<8} {'VORP':<8} {'Tier':<5} {'Age':<4} {'Exp':<4}"
            print(f"{Colors.OKBLUE}{Colors.BOLD}{header}{Colors.ENDC}")
            print(f"{'─' * 120}")
            
            # Table rows with enhanced data
            for i, (_, row) in enumerate(df.iterrows(), 1):
                tier_emoji = "🥇" if row['tier'] == "Tier 1" else "🥈" if row['tier'] == "Tier 2" else "🥉" if row['tier'] == "Tier 3" else "📊"
                injury_icon = "🚨" if row.get('injury_flag', False) else "✅"
                
                line = (f"{i:<4} {row['player']:<20} {row['team']:<4} {row['position']:<3} "
                       f"{row['total_score']:<8.1f} {row.get('vorp_score', 0):<8.1f} {tier_emoji:<5} "
                       f"{row.get('age', 'N/A'):<4} {row.get('experience', 'N/A'):<4}")
                print(line)
            
            print(f"{'─' * 120}")
            
            # Show VORP analysis for the displayed position
            if position:
                pos_df = df[df['position'] == position]
                if not pos_df.empty:
                    print(f"\n{Colors.OKCYAN}📊 {position} VORP Analysis:{Colors.ENDC}")
                    print(f"   Baseline Score: {pos_df['baseline_score'].iloc[0]:.1f}")
                    print(f"   Max VORP: {pos_df['vorp_score'].max():.1f}")
                    print(f"   Avg VORP: {pos_df['vorp_score'].mean():.1f}")
                    print(f"   Players Above Baseline: {len(pos_df[pos_df['vorp_score'] > 0])}")
            
        except Exception as e:
            self.print_error(f"Error displaying rankings: {e}")
    
    def show_player_details(self, player_name: str):
        """Show detailed information about a specific player with VORP analysis"""
        self.print_section_header(f"PLAYER DETAILS: {player_name.upper()}")
        
        try:
            # Load all data sources
            stats_file = Path("data/nfl_player_data.csv")
            news_file = Path("news/player_features.json")
            
            if not stats_file.exists():
                self.print_error("Player stats not found. Run data ingestion first.")
                return
            
            # Load data
            stats_df = pd.read_csv(stats_file)
            # Try different column names for player
            if 'player' in stats_df.columns:
                player_stats = stats_df[stats_df['player'].str.contains(player_name, case=False, na=False)]
            elif 'player_name' in stats_df.columns:
                player_stats = stats_df[stats_df['player_name'].str.contains(player_name, case=False, na=False)]
            else:
                self.print_error("No player column found in data")
                return
            
            if player_stats.empty:
                self.print_error(f"Player '{player_name}' not found")
                return
            
            player_stats = player_stats.iloc[0]
            
            # Display basic info
            print(f"\n{Colors.BOLD}📋 BASIC INFORMATION{Colors.ENDC}")
            print(f"{'─' * 50}")
            player_name_col = 'player' if 'player' in stats_df.columns else 'player_name'
            print(f"Name: {player_stats[player_name_col]}")
            print(f"Position: {player_stats['position']}")
            print(f"Team: {player_stats['team']}")
            print(f"Age: {player_stats.get('age', 'Unknown')}")
            print(f"Experience: {player_stats.get('experience', 'Unknown')} years")
            print(f"Experience Level: {player_stats.get('experience_level', 'Unknown')}")
            
            # Display fantasy stats
            print(f"\n{Colors.BOLD}📊 FANTASY STATISTICS{Colors.ENDC}")
            print(f"{'─' * 50}")
            if 'fantasy_points_ppr' in player_stats.index:
                print(f"2024 Fantasy Points (PPR): {player_stats['fantasy_points_ppr']:.1f}")
            if 'fantasy_points_2025_projected' in player_stats.index:
                print(f"2025 Projected Points: {player_stats['fantasy_points_2025_projected']:.1f}")
            if 'consistency_score' in player_stats.index:
                print(f"Consistency Score: {player_stats['consistency_score']:.2f}")
            if 'weekly_avg' in player_stats.index:
                print(f"Weekly Average: {player_stats['weekly_avg']:.1f}")
            
            # Display news analysis
            if news_file.exists():
                with open(news_file, 'r') as f:
                    news_data = json.load(f)
                
                player_features = news_data.get('player_features', {}).get(player_stats[player_name_col])
                if player_features:
                    print(f"\n{Colors.BOLD}📰 NEWS ANALYSIS{Colors.ENDC}")
                    print(f"{'─' * 50}")
                    print(f"Sentiment Score: {player_features.get('sentiment_score', 0):.2f}")
                    print(f"Buzz Score: {player_features.get('buzz_score', 0):.2f}")
                    print(f"Injury Flag: {'Yes' if player_features.get('injury_flag', False) else 'No'}")
                    
                    topics = player_features.get('topics', [])
                    if topics:
                        print(f"Topics: {', '.join(topics)}")
            
            # Display ranking info with VORP
            if Path("outputs/player_rankings.json").exists():
                ranking_df = self._load_rankings_dataframe()
                player_rank = ranking_df[ranking_df['player'].str.contains(player_name, case=False, na=False)]
                
                if not player_rank.empty:
                    player_rank = player_rank.iloc[0]
                    print(f"\n{Colors.BOLD}🏆 RANKING INFORMATION{Colors.ENDC}")
                    print(f"{'─' * 50}")
                    print(f"Total Score: {player_rank['total_score']:.2f}")
                    print(f"VORP Score: {player_rank.get('vorp_score', 0):.2f}")
                    print(f"Tier: {player_rank['tier']}")
                    print(f"Baseline Score: {player_rank.get('baseline_score', 0):.2f}")
                    
                    # Find position rank (VORP-based)
                    pos_rank = ranking_df[ranking_df['position'] == player_stats['position']]
                    pos_rank = pos_rank.sort_values('vorp_score', ascending=False)
                    player_pos_rank = pos_rank[pos_rank['player'].str.contains(player_name, case=False, na=False)]
                    if not player_pos_rank.empty:
                        actual_rank = pos_rank.index.get_loc(player_pos_rank.index[0]) + 1
                        print(f"Position Rank (VORP): #{actual_rank}")
                    
                    # Show VORP context
                    if player_rank.get('vorp_score', 0) > 0:
                        print(f"{Colors.OKGREEN}💎 This player provides value above replacement level{Colors.ENDC}")
                    else:
                        print(f"{Colors.WARNING}⚠️  This player is below replacement level{Colors.ENDC}")
            
        except Exception as e:
            self.print_error(f"Error showing player details: {e}")
    
    def run_data_ingestion(self, years: Optional[List[int]] = None):
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
    
    def run_ranking(self, use_historical: bool = True, rank_all: bool = True):
        """Run only the player ranking step with enhanced features"""
        self.print_section_header("PLAYER RANKING")
        self.print_info("Generating comprehensive player rankings with VORP analysis...")
        
        try:
            # Generate rankings with historical data
            ranked_df = self.ranker.rank_players()
            if not ranked_df.empty:
                self.ranker.export_rankings(ranked_df)
                self.print_success(f"Generated rankings for {len(ranked_df)} players")
                
                # Display VORP analysis
                self.print_section_header("VORP ANALYSIS")
                self.ranker.print_vorp_analysis(ranked_df)
                
                # Display best value picks
                self.print_section_header("BEST VALUE PICKS")
                # Note: print_best_values method not implemented yet
                
                # Display top players by position
                self.print_section_header("TOP PLAYERS BY POSITION")
                for position in ['QB', 'RB', 'WR', 'TE']:
                    self.ranker.print_top_rankings(ranked_df, position=position, top_n=7)
                
                return True
            else:
                self.print_error("Failed to generate rankings")
                return False
        except Exception as e:
            self.print_error(f"Ranking failed: {e}")
            return False
    
    def run_draft_recommendations(self, top_n: int = 50, pick_position: int = 1,
                                league_size: int = 8, model: str = None,
                                save_output: bool = False, allow_stale_rankings: bool = False,
                                use_ai: bool = False):
        """Run position-aware draft recommendations."""
        self.print_section_header("DRAFT RECOMMENDATIONS")
        
        try:
            # Initialize draft recommender if not already done
            if self.draft_recommender is None:
                self.print_info("Initializing OpenRouter client...")
                self.draft_recommender = DraftRecommender(
                    model=model,
                    allow_stale_rankings=allow_stale_rankings
                )
            
            # Generate recommendations
            mode = "AI-enhanced" if use_ai else "local position-aware"
            self.print_info(f"Generating {mode} draft recommendations for top {top_n} players...")
            recommendations = self.draft_recommender.generate_comprehensive_draft_plan(
                top_n=top_n,
                pick_position=pick_position,
                league_size=league_size,
                use_ai=use_ai
            )
            
            if recommendations.startswith("Error"):
                self.print_error(f"Failed to generate recommendations: {recommendations}")
                return False
            
            # Display recommendations
            self.print_section_header("AI DRAFT RECOMMENDATIONS")
            print(recommendations)
            
            # Save if requested
            if save_output:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"draft_recommendations_{timestamp}.txt"
                self.draft_recommender.save_recommendations(recommendations, filename)
                self.print_success(f"Saved recommendations to outputs/{filename}")
            
            return True
            
        except Exception as e:
            self.print_error(f"Error during draft recommendations: {e}")
            logger.error(f"Draft recommendations error: {e}")
            return False

    def run_openrouter_smoke_test(self, model: str = None):
        """Verify OpenRouter env loading and basic chat completion connectivity."""
        self.print_section_header("OPENROUTER SMOKE TEST")

        client = OpenRouterClient(model=model)
        self.print_info(f"Model: {client.model}")
        self.print_info(f"API key visible: {bool(client.api_key)}")

        response = client.chat(
            messages=[
                {"role": "system", "content": "You are a terse connectivity test."},
                {"role": "user", "content": "Reply with exactly: OpenRouter OK"},
            ],
            temperature=0,
            max_tokens=16,
            timeout=30,
        )
        if response.startswith("Error:"):
            self.print_error(response)
            return False

        print(response)
        self.print_success("OpenRouter smoke test completed")
        return True

    def run_smoke_test(self, pick_position: int = 1, league_size: int = 8):
        """Run local health checks for rankings and draft recommendations."""
        self.print_section_header("LOCAL SMOKE TEST")

        try:
            ranking_file = Path("outputs/player_rankings.json")
            if not ranking_file.exists():
                self.print_error("Missing outputs/player_rankings.json. Run --rank-only first.")
                return False

            with open(ranking_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
            rankings = payload.get("rankings", []) if isinstance(payload, dict) else payload
            if not rankings:
                self.print_error("Ranking file has no players")
                return False

            first_player = rankings[0]
            required_player_fields = {
                "name", "pos", "team", "score", "VORP", "projected_fantasy_points",
                "projection_rank", "score_breakdown",
            }
            missing_fields = required_player_fields - set(first_player)
            if missing_fields:
                self.print_error(f"Ranking schema missing fields: {', '.join(sorted(missing_fields))}")
                return False
            if "news_component" not in first_player.get("score_breakdown", {}):
                self.print_error("Ranking score_breakdown missing news_component")
                return False

            recommender = DraftRecommender(allow_stale_rankings=False)
            rankings_df = recommender.load_ranking_data()
            board = recommender.prepare_draft_board(rankings_df)
            if board.empty:
                self.print_error("Draft board is empty after filtering")
                return False

            positions = set(board["position"].dropna().unique())
            missing_positions = {"QB", "RB", "WR", "TE"} - positions
            if missing_positions:
                self.print_error(f"Draft board missing positions: {', '.join(sorted(missing_positions))}")
                return False

            picks = recommender._calculate_snake_picks(pick_position, league_size, rounds=2)
            if len(picks) != 2 or picks[0] != pick_position:
                self.print_error("Snake pick calculation failed")
                return False

            plan = recommender.generate_local_draft_plan(
                board,
                pick_position=pick_position,
                league_size=league_size,
                rounds=1,
            )
            if "Likely available board:" not in plan or "Possible fallers" not in plan:
                self.print_error("Draft plan did not include availability pools")
                return False

            self.print_success(f"Ranking metadata target season: {metadata.get('target_season', 'unknown')}")
            self.print_success(f"Validated {len(rankings_df)} ranked players and {len(board)} draft-board players")
            self.print_success(f"Snake picks for slot {pick_position}: {', '.join(str(p) for p in picks)}")
            self.print_success("Local smoke test completed")
            return True

        except Exception as e:
            self.print_error(f"Smoke test failed: {e}")
            logger.error(f"Smoke test error: {e}")
            return False

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="🏈 NFL Fantasy Draft Assistant - AI-powered fantasy football analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/cli.py --pipeline                    # Run complete analysis
  python scripts/cli.py --pipeline --skip-news        # Run pipeline without news refresh
  python scripts/cli.py --rankings --position WR      # Show top WR rankings
  python scripts/cli.py --player "Patrick Mahomes"    # Show player details
  python scripts/cli.py --data-only                   # Only fetch player data
  python scripts/cli.py --news-only                   # Only fetch and analyze news
  python scripts/cli.py --draft-recommendations       # Generate fast position-aware draft recommendations
  python scripts/cli.py --smoke-test                  # Validate local rankings and draft logic
  python scripts/cli.py --draft-recommendations --top 30 --save-recommendations  # Custom recommendations
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
    action_group.add_argument('--draft-recommendations', action='store_true',
                             help='Generate position-aware draft recommendations')
    action_group.add_argument('--smoke-test', action='store_true',
                             help='Validate local rankings, schema, and draft recommendation logic')
    action_group.add_argument('--openrouter-smoke-test', action='store_true',
                             help='Verify OpenRouter env loading and API connectivity')
    action_group.add_argument('--build-board', action='store_true',
                             help='Build position-first outputs/draft_board.json')
    action_group.add_argument('--validate-board', action='store_true',
                             help='Validate draft board data health and freshness')
    action_group.add_argument('--show-board', action='store_true',
                             help='Show top player priorities by position')
    action_group.add_argument('--fetch-projections', action='store_true',
                             help='Fetch current projections/ADP and write source metadata')
    action_group.add_argument('--validate-projections', action='store_true',
                             help='Validate projection provenance, coverage, and identity')
    
    # Filtering options
    parser.add_argument('--position', type=str, choices=['QB', 'RB', 'WR', 'TE', 'K', 'DST'],
                       help='Filter by position (for rankings)')
    parser.add_argument('--top', type=int, default=10, metavar='N',
                       help='Show top N players (default: 10)')
    parser.add_argument('--board-top', type=int, default=None, metavar='N',
                       help='Override the default per-position board limits')
    parser.add_argument('--scoring', choices=['standard', 'half_ppr', 'ppr'], default='half_ppr',
                       help='League scoring format for board metadata (default: half_ppr)')
    parser.add_argument('--season', type=int, default=datetime.now().year,
                       help='Target fantasy season (default: current year)')
    parser.add_argument('--exclude-injured', action='store_true',
                       help='Exclude injured players from rankings')
    parser.add_argument('--sort-by', type=str, choices=['vorp', 'score', 'buzz', 'consistency'], default='vorp',
                       help='Sort rankings by (default: vorp for better draft strategy)')
    
    # Pipeline options
    parser.add_argument('--years', type=int, nargs='+', default=None,
                       help='Years of data to analyze (default: most recent 3 completed seasons)')
    parser.add_argument('--news-age', type=int, default=24, metavar='HOURS',
                       help='Maximum age of news headlines in hours (default: 24)')
    parser.add_argument('--force-refresh', action='store_true',
                       help='Force refresh of existing data')
    parser.add_argument('--skip-news', action='store_true',
                       help='Skip news fetching and analysis (use existing news data if available)')
    
    # Draft recommendations options
    parser.add_argument('--openrouter-model', type=str, default=None,
                       help='OpenRouter model slug (default: OPENROUTER_MODEL or openai/gpt-4o-mini)')
    parser.add_argument('--use-ai', action='store_true',
                       help='Ask OpenRouter to write the draft analysis after building the local board')
    parser.add_argument('--pick-position', type=int, default=1,
                       help='Your snake draft position (default: 1)')
    parser.add_argument('--league-size', type=int, default=8,
                       help='Number of teams in the league (default: 8)')
    parser.add_argument('--allow-stale-rankings', action='store_true',
                       help='Allow legacy/stale rankings for inspection only')
    parser.add_argument('--save-recommendations', action='store_true',
                       help='Save draft recommendations to file')
    
    args = parser.parse_args()
    
    # Initialize CLI
    cli = FantasyCLI()
    
    try:
        if args.pipeline:
            success = cli.run_full_pipeline(
                years=args.years,
                max_news_age=args.news_age,
                force_refresh=args.force_refresh,
                skip_news=args.skip_news
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
            success = cli.run_ranking(rank_all=True)
            sys.exit(0 if success else 1)
            
        elif args.draft_recommendations:
            success = cli.run_draft_recommendations(
                top_n=args.top,
                pick_position=args.pick_position,
                league_size=args.league_size,
                model=args.openrouter_model,
                save_output=args.save_recommendations,
                allow_stale_rankings=args.allow_stale_rankings,
                use_ai=args.use_ai
            )
            sys.exit(0 if success else 1)

        elif args.openrouter_smoke_test:
            success = cli.run_openrouter_smoke_test(model=args.openrouter_model)
            sys.exit(0 if success else 1)

        elif args.smoke_test:
            success = cli.run_smoke_test(
                pick_position=args.pick_position,
                league_size=args.league_size,
            )
            sys.exit(0 if success else 1)

        elif args.build_board:
            success = cli.build_draft_board(
                top_n=args.board_top,
                league_size=args.league_size,
                scoring=args.scoring,
            )
            sys.exit(0 if success else 1)

        elif args.validate_board:
            success = cli.validate_draft_board()
            sys.exit(0 if success else 1)

        elif args.show_board:
            success = cli.show_draft_board(position=args.position, top_n=args.top)
            sys.exit(0 if success else 1)

        elif args.fetch_projections:
            success = cli.fetch_projections(season=args.season)
            sys.exit(0 if success else 1)

        elif args.validate_projections:
            success = cli.validate_projections(season=args.season)
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

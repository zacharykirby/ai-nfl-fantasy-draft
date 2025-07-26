#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Quick Ranking Tool

A simple script to quickly generate fantasy draft rankings with different player counts.
"""

import argparse
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Quick Fantasy Draft Rankings')
    parser.add_argument('--players', type=int, choices=[10, 20, 30, 40, 50, 100], default=40,
                       help='Number of players to rank (default: 40)')
    parser.add_argument('--rank-all', action='store_true',
                       help='Rank all available players (overrides --players)')
    parser.add_argument('--refresh-data', action='store_true',
                       help='Refresh player data before ranking')
    parser.add_argument('--position', type=str, choices=['QB', 'RB', 'WR', 'TE', 'ALL'], default='ALL',
                       help='Position to focus on (default: ALL)')
    parser.add_argument('--top-n', type=int, default=10,
                       help='Number of top players to display per position (default: 10)')
    
    args = parser.parse_args()
    
    print("🏈 NFL Fantasy Draft Assistant - Quick Rankings")
    print("=" * 50)
    
    if args.rank_all:
        print(f"📊 Ranking ALL available players")
        print(f"🎯 Position focus: {args.position}")
        print(f"📈 Displaying top {args.top_n} players per position")
    else:
        print(f"📊 Ranking {args.players} players")
        print(f"🎯 Position focus: {args.position}")
        print(f"📈 Displaying top {args.top_n} players per position")
    
    # Step 1: Generate player data if needed or requested
    if args.refresh_data or not Path("data/enhanced_player_stats.csv").exists():
        max_players = 100 if args.rank_all else args.players
        if not run_command(
            f"python scripts/generate_player_data.py --max-players {max_players} --use-curated",
            "Generating player data"
        ):
            return False
    
    # Step 2: Run the ranking system
    if args.rank_all:
        rank_cmd = f"python scripts/ranker.py --rank-all --top-n {args.top_n}"
    else:
        rank_cmd = f"python scripts/ranker.py --max-players {args.players} --top-n {args.top_n}"
    
    if args.position != 'ALL':
        rank_cmd += f" --position {args.position}"
    
    if not run_command(rank_cmd, "Generating rankings"):
        return False
    
    print(f"\n🎉 Ranking complete! Generated rankings for {args.players} players.")
    print(f"📁 Results saved to: outputs/")
    print(f"📊 Summary: outputs/ranking_summary.json")
    
    # Show quick summary
    try:
        import json
        with open("outputs/ranking_summary.json", 'r') as f:
            summary = json.load(f)
        
        print(f"\n📈 Quick Summary:")
        print(f"   Total players: {summary['total_players']}")
        print(f"   Positions: {', '.join([f'{pos}({count})' for pos, count in summary['positions'].items()])}")
        print(f"   Tier distribution: {dict(summary['tiers'])}")
        
        # Show top 5 by VORP
        if 'best_values_by_vorp' in summary:
            print(f"\n🏆 Top 5 by VORP:")
            for i, player in enumerate(summary['best_values_by_vorp'][:5], 1):
                print(f"   {i}. {player['player']} ({player['position']}) - VORP: {player['vorp_score']:.1f}")
        
    except Exception as e:
        print(f"Could not load summary: {e}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
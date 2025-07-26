#!/usr/bin/env python3
"""
Demo script for the NFL Fantasy Draft Assistant CLI

This script demonstrates how to use the CLI with various commands
and shows the expected outputs.
"""

import subprocess
import sys
import time
from pathlib import Path

def run_command(command: str, description: str):
    """Run a CLI command and display the output"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Command: {command}")
    print(f"{'='*60}")
    
    try:
        # Use shell=True to handle quotes properly
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
    except Exception as e:
        print(f"Error running command: {e}")

def main():
    """Run demo commands"""
    print("🏈 NFL Fantasy Draft Assistant CLI Demo")
    print("This demo shows how to use the CLI with various commands")
    
    # Check if we're in the right directory
    if not Path("scripts/cli.py").exists():
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Demo 1: Show help
    run_command("python scripts/cli.py --help", "Show CLI help and available options")
    
    # Demo 2: Show rankings (if they exist)
    if Path("outputs/ranked_all_players.csv").exists():
        run_command("python scripts/cli.py --rankings --top 5", "Show top 5 players across all positions")
        run_command("python scripts/cli.py --rankings --position WR --top 3", "Show top 3 WRs")
        run_command("python scripts/cli.py --rankings --position QB --sort-by buzz", "Show QBs sorted by news buzz")
    else:
        print("\n⚠️  No ranking data found. Run the pipeline first:")
        print("   python scripts/cli.py --pipeline")
    
    # Demo 3: Show player details (if data exists)
    if Path("data/enhanced_player_stats.csv").exists():
        run_command('python scripts/cli.py --player "Patrick Mahomes"', "Show detailed info for Patrick Mahomes")
    else:
        print("\n⚠️  No player data found. Run data ingestion first:")
        print("   python scripts/cli.py --data-only")
    
    print(f"\n{'='*60}")
    print("🎯 Demo completed! Try these additional commands:")
    print(f"{'='*60}")
    print("• python scripts/cli.py --pipeline                    # Run complete analysis")
    print("• python scripts/cli.py --data-only                   # Only fetch player data")
    print("• python scripts/cli.py --news-only                   # Only fetch and analyze news")
    print("• python scripts/cli.py --rankings --exclude-injured  # Show rankings excluding injured players")
    print('• python scripts/cli.py --player "Christian McCaffrey" # Show player details')

if __name__ == "__main__":
    main() 
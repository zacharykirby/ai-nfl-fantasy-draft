#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Pipeline Demo

This script demonstrates the complete functionality of the fantasy football
pipeline with beautiful output and real examples.
"""

import sys
import os
import time
from pathlib import Path

# Add the scripts directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cli import FantasyCLI, Colors

def print_demo_banner():
    """Print a beautiful demo banner"""
    banner = f"""
{Colors.HEADER}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🏈 NFL FANTASY DRAFT ASSISTANT 🏈                        ║
║                                                                              ║
║                           🎯 PIPELINE DEMO 🎯                              ║
║                                                                              ║
║  Demonstrating the complete AI-powered fantasy football analysis pipeline   ║
╚══════════════════════════════════════════════════════════════════════════════╝
{Colors.ENDC}"""
    print(banner)

def demo_data_ingestion():
    """Demonstrate data ingestion capabilities"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}📊 DATA INGESTION DEMO{Colors.ENDC}")
    print("=" * 50)
    
    cli = FantasyCLI()
    
    print("🔍 Fetching comprehensive NFL player data...")
    print("   • Seasonal statistics (2022-2024)")
    print("   • Weekly performance data")
    print("   • Roster information")
    print("   • Combine measurements")
    print("   • Fantasy points and consistency metrics")
    
    # Run data ingestion
    cli.run_data_ingestion()
    
    print(f"\n{Colors.OKGREEN}✅ Data ingestion complete!{Colors.ENDC}")

def demo_news_pipeline():
    """Demonstrate news analysis capabilities"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}📰 NEWS ANALYSIS DEMO{Colors.ENDC}")
    print("=" * 50)
    
    cli = FantasyCLI()
    
    print("🔍 Fetching and analyzing fantasy football news...")
    print("   • Real-time headlines from multiple sources")
    print("   • AI-powered sentiment analysis")
    print("   • Player-specific feature extraction")
    print("   • Injury and role change detection")
    print("   • Buzz and hype scoring")
    
    # Run news pipeline
    cli.run_news_pipeline()
    
    print(f"\n{Colors.OKGREEN}✅ News analysis complete!{Colors.ENDC}")

def demo_ranking():
    """Demonstrate ranking capabilities"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}📈 PLAYER RANKING DEMO{Colors.ENDC}")
    print("=" * 50)
    
    cli = FantasyCLI()
    
    print("🧮 Calculating comprehensive player rankings...")
    print("   • Historical performance analysis")
    print("   • Injury risk assessment")
    print("   • Team context evaluation")
    print("   • News sentiment integration")
    print("   • Consistency scoring")
    print("   • Position-specific adjustments")
    
    # Run ranking
    cli.run_ranking()
    
    print(f"\n{Colors.OKGREEN}✅ Player ranking complete!{Colors.ENDC}")

def demo_cli_features():
    """Demonstrate CLI features"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}🖥️ CLI FEATURES DEMO{Colors.ENDC}")
    print("=" * 50)
    
    cli = FantasyCLI()
    
    print("🎯 Top 5 Quarterbacks:")
    cli.show_rankings(position="QB", top_n=5)
    
    print(f"\n🎯 Top 5 Running Backs:")
    cli.show_rankings(position="RB", top_n=5)
    
    print(f"\n🎯 Top 5 Wide Receivers:")
    cli.show_rankings(position="WR", top_n=5)
    
    print(f"\n🎯 Top 5 Tight Ends:")
    cli.show_rankings(position="TE", top_n=5)
    
    print(f"\n🔍 Player Detail Example - Christian McCaffrey:")
    cli.show_player_details("Christian McCaffrey")

def demo_full_pipeline():
    """Demonstrate the complete pipeline"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}🔄 COMPLETE PIPELINE DEMO{Colors.ENDC}")
    print("=" * 50)
    
    cli = FantasyCLI()
    
    print("🚀 Running the complete fantasy football analysis pipeline...")
    print("   This will:")
    print("   1. Fetch and process player data")
    print("   2. Collect and analyze news")
    print("   3. Calculate comprehensive rankings")
    print("   4. Generate position-specific outputs")
    
    start_time = time.time()
    
    # Run full pipeline
    cli.run_full_pipeline()
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n{Colors.OKGREEN}✅ Complete pipeline finished in {duration:.1f} seconds!{Colors.ENDC}")

def main():
    """Main demo function"""
    print_demo_banner()
    
    try:
        # Demo individual components
        demo_data_ingestion()
        time.sleep(2)
        
        demo_news_pipeline()
        time.sleep(2)
        
        demo_ranking()
        time.sleep(2)
        
        demo_cli_features()
        time.sleep(2)
        
        # Demo complete pipeline
        demo_full_pipeline()
        
        print(f"\n{Colors.HEADER}{Colors.BOLD}")
        print("🎉 DEMO COMPLETE!")
        print("=" * 50)
        print("The NFL Fantasy Draft Assistant is ready for your draft!")
        print("Use 'python scripts/cli.py --help' to see all available commands.")
        print(f"{Colors.ENDC}")
        
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Demo interrupted by user{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}Error during demo: {str(e)}{Colors.ENDC}")

if __name__ == "__main__":
    main() 
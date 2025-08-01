#!/usr/bin/env python3
"""
NFL Fantasy Draft Recommendation System
Uses Ollama LLM to analyze top VORP-ranked players and suggest optimal draft pick ordering

This script:
1. Loads the ranking data and VORP scores
2. Identifies top players by VORP across all positions
3. Sends data to Ollama for strategic analysis
4. Outputs draft recommendations with reasoning
"""

import pandas as pd
import json
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DraftRecommender:
    """Draft recommendation system using Ollama LLM analysis"""
    
    def __init__(self, ollama_url: str = None, model: str = "deepseek-r1"):
        # Use OLLAMA_HOST environment variable or default to network address
        if ollama_url is None:
            import os
            ollama_host = os.getenv('OLLAMA_HOST', '127.0.0.1')
            # Handle both IP addresses and full URLs
            if ollama_host.startswith('http'):
                self.ollama_url = ollama_host
            else:
                self.ollama_url = f"http://{ollama_host}:11434"
        else:
            self.ollama_url = ollama_url
        self.model = model
        self.rankings_dir = Path("outputs")
        
    def load_ranking_data(self) -> pd.DataFrame:
        """Load the latest ranking data from player_rankings.json"""
        try:
            # Load the player rankings JSON file
            rankings_file = self.rankings_dir / "player_rankings.json"
            if not rankings_file.exists():
                raise FileNotFoundError(f"Ranking data not found at {rankings_file}")
            
            with open(rankings_file, 'r') as f:
                rankings_data = json.load(f)
            
            # Convert JSON data to DataFrame
            df = pd.DataFrame(rankings_data)
            
            # Standardize column names to match expected format
            column_mapping = {
                'pos': 'position',
                'score': 'total_score',
                'VORP': 'vorp_score'
            }
            
            # Rename columns that exist
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure required columns exist with defaults
            required_columns = {
                'name': 'Unknown',
                'position': 'Unknown', 
                'team': 'Unknown',
                'total_score': 0.0,
                'vorp_score': 0.0,
                'tier': 'Tier 5',
                'age': 0,
                'projected_2025_pts': 0.0,
                'raw_score': 0.0,
                'consistency_score': 0.5,
                'ceiling_potential': 0.5,
                'bye_week': 'N/A'
            }
            
            for col, default_val in required_columns.items():
                if col not in df.columns:
                    df[col] = default_val
            
            # Convert numeric columns
            numeric_columns = ['total_score', 'vorp_score', 'age', 'projected_2025_pts', 'raw_score', 'consistency_score', 'ceiling_potential']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            logger.info(f"Loaded {len(df)} ranked players from {rankings_file}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading ranking data: {e}")
            raise
    

    
    def get_top_vorp_players(self, df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
        """Get top players by VORP score across all positions"""
        try:
            # Sort by VORP score and get top players
            top_players = df.nlargest(top_n, 'vorp_score').copy()
            
            # Add position rank for context
            top_players['position_rank'] = top_players.groupby('position')['vorp_score'].rank(method='dense', ascending=False)
            
            logger.info(f"Selected top {len(top_players)} players by VORP for analysis")
            return top_players
            
        except Exception as e:
            logger.error(f"Error getting top VORP players: {e}")
            raise
    
    def create_comprehensive_draft_plan(self, top_players: pd.DataFrame, pick_position: int = 1, league_size: int = 8) -> str:
        """Create a streamlined draft plan with 5 picks per round focusing on VORP and bye weeks"""
        
        # Create simplified player data for the prompt
        player_data = []
        for _, player in top_players.iterrows():
            player_info = {
                'name': player['name'],
                'position': player['position'],
                'team': player['team'],
                'vorp_score': round(player['vorp_score'], 2),
                'bye_week': str(player.get('bye_week', 'N/A'))
            }
            player_data.append(player_info)

        # Calculate snake draft picks
        snake_picks = self._calculate_snake_picks(pick_position, league_size)
        
        prompt = f"""Create a realistic fantasy football draft strategy for an 8-team league, drafting from position {pick_position}.

Available Players: {json.dumps(player_data, indent=2)}

Draft Philosophy:
- Build a BALANCED roster, not just chase the highest VORP scores
- Consider positional scarcity and replacement level differences
- Maintain bye week diversity to avoid roster management nightmares
- Adapt to realistic draft flow - don't assume your targets will always be available
- Balance floor vs ceiling based on draft position and league competitiveness

Roster Construction Guidelines:
- Early rounds (1-3): Focus on weekly starters with high floors
- Mid rounds (4-6): Mix of reliable starters and high-upside plays
- Late rounds (7-8): Handcuffs, lottery tickets, and bye week fill-ins
- Target roster: 2 RB, 3 WR, 1 QB, 1 TE, 1 K, 1 DST (adjust based on league settings)

For each round, provide:
1. PRIMARY TARGET: Your ideal pick if available
2. PIVOT OPTIONS: 3-4 realistic alternatives if your target is gone
3. STRATEGY NOTE: Brief explanation of round strategy and positional priorities

Format each player as: "Player Name - Position - Team (VORP: X.X | Bye: Week Y | Floor/Ceiling Assessment)"

Consider these realistic scenarios:
- Other drafters may reach for popular players
- Position runs can happen unexpectedly
- Value can shift dramatically based on who's already been picked
- Sometimes the "wrong" pick is the right pick for roster construction

## FLEXIBLE DRAFT STRATEGY - Position {pick_position}

**ROUND 1 (Pick {snake_picks[0]}) - Secure Your Foundation**
Primary Target: 
Pivot Options:
1.
2.
3.
4.
Strategy Note: 

**ROUND 2 (Pick {snake_picks[1]}) - Complement Round 1**
Primary Target:
Pivot Options:
1.
2.
3.
4.
Strategy Note:

**ROUND 3 (Pick {snake_picks[2]}) - Address Positional Need**
Primary Target:
Pivot Options:
1.
2.
3.
4.
Strategy Note:

**ROUND 4 (Pick {snake_picks[3]}) - Value vs Need Balance**
Primary Target:
Pivot Options:
1.
2.
3.
4.
Strategy Note:

**ROUND 5 (Pick {snake_picks[4]}) - Starter or Upside Play**
Primary Target:
Pivot Options:
1.
2.
3.
4.
Strategy Note:

**ROUND 6 (Pick {snake_picks[5]}) - Fill Remaining Starters**
Primary Target:
Pivot Options:
1.
2.
3.
4.
Strategy Note:

**ROUND 7 (Pick {snake_picks[6]}) - Depth and Lottery Tickets**
Primary Target:
Pivot Options:
1.
2.
3.
4.
Strategy Note:

**ROUND 8 (Pick {snake_picks[7]}) - Final Roster Spot**
Primary Target:
Pivot Options:
1.
2.
3.
4.
Strategy Note:

**POST-DRAFT ROSTER CONSTRUCTION CHECK:**
- Do you have 2+ startable RBs?
- Do you have 3+ startable WRs?
- Are your bye weeks reasonably spread out?
- Do you have at least 2 high-ceiling players?
- Do you have handcuffs for your top RBs if available?

Remember: The best draft is the one that builds a complete, balanced roster - not the one that looks best on paper immediately after the draft."""

        return prompt

    def _calculate_snake_picks(self, pick_position: int, league_size: int) -> List[int]:
        """Calculate all picks for a given draft position in snake draft"""
        picks = []
        for round_num in range(1, 16):  # 15 rounds
            if round_num % 2 == 1:  # Odd rounds (1, 3, 5, etc.)
                pick = pick_position
            else:  # Even rounds (2, 4, 6, etc.)
                pick = league_size - pick_position + 1
            
            picks.append(pick)
        return picks

    def generate_comprehensive_draft_plan(self, top_n: int = 50, pick_position: int = 1, league_size: int = 8) -> str:
        """Generate comprehensive draft plan for 8-team league"""
        try:
            logger.info(f"Generating comprehensive draft plan for {league_size}-team league, pick position {pick_position}...")
            
            # Load ranking data
            df = self.load_ranking_data()
            
            # Get top VORP players
            top_players = self.get_top_vorp_players(df, top_n)
            
            # Print summary of players being analyzed
            self.print_player_summary(top_players)
            
            # Create comprehensive analysis prompt
            prompt = self.create_comprehensive_draft_plan(top_players, pick_position, league_size)
            
            # Get LLM analysis
            logger.info("Requesting comprehensive draft analysis from Ollama...")
            recommendations = self.query_ollama(prompt)
            
            # Check if Ollama failed and provide fallback
            if recommendations.startswith("Error:"):
                logger.warning("Ollama connection failed, generating fallback recommendations...")
                recommendations = self.generate_fallback_comprehensive_plan(top_players, pick_position, league_size)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating comprehensive draft plan: {e}")
            return f"Error generating draft plan: {str(e)}"

    def generate_fallback_comprehensive_plan(self, top_players: pd.DataFrame, pick_position: int, league_size: int) -> str:
        """Generate fallback comprehensive draft plan when Ollama is not available"""
        try:
            snake_picks = self._calculate_snake_picks(pick_position, league_size)
            
            recommendations = []
            recommendations.append("## COMPREHENSIVE DRAFT PLAN - 8-TEAM LEAGUE")
            recommendations.append(f"**Draft Position:** {pick_position} | **Your Picks:** {snake_picks}")
            recommendations.append("(Generated without LLM analysis - Ollama unavailable)")
            recommendations.append("")
            
            # Round-by-round strategy
            recommendations.append("### ROUND-BY-ROUND STRATEGY")
            recommendations.append("")
            
            # Group players by position for easier analysis
            qbs = top_players[top_players['position'] == 'QB'].head(8)
            rbs = top_players[top_players['position'] == 'RB'].head(16)
            wrs = top_players[top_players['position'] == 'WR'].head(20)
            tes = top_players[top_players['position'] == 'TE'].head(6)
            
            # Round 1-3 recommendations
            for round_num in [1, 2, 3]:
                recommendations.append(f"**ROUND {round_num} (Pick {snake_picks[round_num-1]})**")
                
                if round_num == 1:
                    # First round - prioritize highest VORP
                    primary = top_players.iloc[0]
                    fallback1 = top_players.iloc[1]
                    fallback2 = top_players.iloc[2]
                elif round_num == 2:
                    # Second round - consider position scarcity
                    primary = top_players.iloc[3]
                    fallback1 = top_players.iloc[4]
                    fallback2 = top_players.iloc[5]
                else:
                    # Third round - balance position needs
                    primary = top_players.iloc[6]
                    fallback1 = top_players.iloc[7]
                    fallback2 = top_players.iloc[8]
                
                recommendations.append(f"**Primary Target:** {primary['name']} - {primary['position']} - {primary['team']}")
                recommendations.append(f"  - VORP: {primary['vorp_score']:.1f} | Bye: Week {primary.get('bye_week', 'N/A')}")
                recommendations.append(f"  - Reasoning: Best available VORP value")
                recommendations.append("")
                
                recommendations.append("**Fallback Options:**")
                recommendations.append(f"1. {fallback1['name']} - {fallback1['position']} - {fallback1['team']} (VORP: {fallback1['vorp_score']:.1f} | Bye: {fallback1.get('bye_week', 'N/A')})")
                recommendations.append(f"2. {fallback2['name']} - {fallback2['position']} - {fallback2['team']} (VORP: {fallback2['vorp_score']:.1f} | Bye: {fallback2.get('bye_week', 'N/A')})")
                recommendations.append("")
            
            # Positional strategy
            recommendations.append("### POSITIONAL STRATEGY")
            recommendations.append("")
            recommendations.append("**QB Strategy:** In 8-team leagues, QB depth is plentiful. Target QB in rounds 6-8 unless elite QB falls.")
            recommendations.append("**RB Strategy:** RB scarcity is real. Target RB1 in first 2 rounds, RB2 by round 4.")
            recommendations.append("**WR Strategy:** WR depth allows patience. Target WR1 in rounds 1-3, WR2 in rounds 4-6.")
            recommendations.append("**TE Strategy:** Steep drop-off after top 3-4 TEs. Target TE1 in rounds 3-5.")
            recommendations.append("")
            
            # Bye week management
            recommendations.append("### BYE WEEK MANAGEMENT")
            recommendations.append("")
            recommendations.append("**Bye Week Conflicts to Monitor:**")
            bye_weeks = top_players['bye_week'].value_counts()
            for bye_week, count in bye_weeks.head(5).items():
                if bye_week != 'N/A' and count > 2:
                    recommendations.append(f"- Week {bye_week}: {count} top players")
            recommendations.append("")
            recommendations.append("**Strategy:** Avoid having more than 2 starters with same bye week")
            recommendations.append("")
            
            # Draft board analysis
            recommendations.append("### DRAFT BOARD ANALYSIS")
            recommendations.append("")
            recommendations.append("**Players Likely Available at Your Picks:**")
            for round_num in range(1, 9):
                pick_num = snake_picks[round_num-1]
                # Estimate which players might be available
                start_idx = (round_num - 1) * 8
                end_idx = start_idx + 8
                available_players = top_players.iloc[start_idx:end_idx]
                
                recommendations.append(f"**Round {round_num} (Pick {pick_num}):**")
                for _, player in available_players.head(3).iterrows():
                    recommendations.append(f"  - {player['name']} ({player['position']}) - VORP: {player['vorp_score']:.1f} | Bye: {player.get('bye_week', 'N/A')}")
                recommendations.append("")
            
            # Contingency plans
            recommendations.append("### CONTINGENCY PLANS")
            recommendations.append("")
            recommendations.append("**If RB Run Happens Early:** Pivot to WR-heavy strategy, target RB2 in rounds 4-6")
            recommendations.append("**If WR Run Happens Early:** Double up on RBs early, target WR2 in rounds 5-7")
            recommendations.append("**If TE Run Happens Early:** Take TE1 earlier than planned, adjust other positions")
            recommendations.append("**End-Game Strategy:** Target high-upside players and handcuffs in final rounds")
            recommendations.append("")
            
            # Draft cheatsheet
            recommendations.append("### DRAFT CHEATSHEET")
            recommendations.append("")
            recommendations.append("- ♦ RB scarcity is critical - don't wait too long for RB2")
            recommendations.append("- ♦ WR depth allows for patience in middle rounds")
            recommendations.append("- ♦ QB can wait until rounds 6-8 in 8-team leagues")
            recommendations.append("- ♦ TE has steep drop-off after top 3-4 options")
            recommendations.append("- ♦ Monitor bye weeks to avoid conflicts")
            recommendations.append("- ♦ In 8-team leagues, focus on upside over floor")
            recommendations.append("- ♦ Don't reach for positions - let value come to you")
            
            return "\n".join(recommendations)
            
        except Exception as e:
            logger.error(f"Error generating fallback comprehensive plan: {e}")
            return "Error generating fallback comprehensive plan"
    
    def query_ollama(self, prompt: str) -> str:
        """Send prompt to Ollama and get response"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
            }
            
            logger.info(f"Sending draft analysis request to Ollama ({self.model})...")
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', 'No response received')
                
                # Filter out <think> sections from reasoning models
                response_text = self._filter_think_sections(response_text)
                
                return response_text
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return f"Error: Ollama API returned status {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to Ollama: {e}")
            return f"Error: Could not connect to Ollama at {self.ollama_url}"
        except Exception as e:
            logger.error(f"Error querying Ollama: {e}")
            return f"Error: {str(e)}"
    
    def _filter_think_sections(self, text: str) -> str:
        """Remove <think> sections from LLM responses"""
        import re
        
        # Remove <think>...</think> sections
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # Remove <thinking>...</thinking> sections (alternative format)
        text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
        
        # Remove <reasoning>...</reasoning> sections
        text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)
        
        # Remove standalone <think> tags
        text = re.sub(r'<think>', '', text)
        text = re.sub(r'</think>', '', text)
        
        # Clean up extra whitespace and newlines
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Remove excessive blank lines
        text = text.strip()
        
        return text
    
    def print_player_summary(self, top_players: pd.DataFrame) -> None:
        """Print a summary of the top players being analyzed"""
        print("\n" + "="*80)
        print("🏈 TOP PLAYERS BY VORP - DRAFT ANALYSIS")
        print("="*80)
        print(f"{'Rank':<4} {'Player':<20} {'Pos':<3} {'Team':<4} {'VORP':<6} {'Score':<6} {'Tier':<4} {'Pos Rank':<8}")
        print("-"*80)
        
        for i, (_, player) in enumerate(top_players.iterrows(), 1):
            print(f"{i:<4} {player['name']:<20} {player['position']:<3} "
                  f"{player['team']:<4} {player['vorp_score']:<6.1f} {player['total_score']:<6.1f} "
                  f"{player['tier']:<6} {int(player['position_rank']):<8}")
        
        print("="*80)
        
        # Position distribution
        print("\n📊 POSITION DISTRIBUTION:")
        pos_counts = top_players['position'].value_counts()
        for pos, count in pos_counts.items():
            print(f"   {pos}: {count} players")
        
        # Tier distribution
        print("\n🏆 TIER DISTRIBUTION:")
        tier_counts = top_players['tier'].value_counts()
        for tier, count in tier_counts.items():
            print(f"   {tier}: {count} players")
    
    def save_recommendations(self, recommendations: str, filename: str = None) -> None:
        """Save recommendations to file"""
        try:
            if filename is None:
                filename = f"draft_recommendations.txt"
            
            output_file = self.rankings_dir / filename
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("NFL FANTASY DRAFT RECOMMENDATIONS\n")
                f.write("Generated by Ollama LLM Analysis\n")
                f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*80 + "\n\n")
                f.write(recommendations)
            
            logger.info(f"Saved draft recommendations to {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving recommendations: {e}")

def main():
    """Main function to run draft recommendations"""
    parser = argparse.ArgumentParser(description='NFL Fantasy Draft Recommendation System')
    parser.add_argument('--top-n', type=int, default=50,
                       help='Number of top VORP players to analyze (default: 50)')
    parser.add_argument('--pick-position', type=int, default=1,
                       help='Your draft position (1-8 for 8-team league, default: 1)')
    parser.add_argument('--league-size', type=int, default=8,
                       help='Number of teams in league (default: 8)')
    parser.add_argument('--ollama-url', type=str, default=None,
                       help='Ollama API URL (default: uses OLLAMA_HOST env var or 127.0.0.1)')
    parser.add_argument('--model', type=str, default='deepseek-r1',
                       help='Ollama model to use (default: deepseek-r1)')
    parser.add_argument('--save', action='store_true',
                       help='Save recommendations to file')
    parser.add_argument('--output-file', type=str, default=None,
                       help='Output filename (default: auto-generated)')
    parser.add_argument('--print-prompt', action='store_true',
                       help='Print only the prompt and exit (for copy/paste)')
    
    args = parser.parse_args()
    
    try:
        # Initialize recommender
        recommender = DraftRecommender(
            ollama_url=args.ollama_url,
            model=args.model
        )
        
        # If --print-prompt is specified, just print the prompt and exit
        if args.print_prompt:
            # Load ranking data
            df = recommender.load_ranking_data()
            
            # Get top VORP players
            top_players = recommender.get_top_vorp_players(df, args.top_n)
            
            # Create and print the prompt
            prompt = recommender.create_comprehensive_draft_plan(top_players, args.pick_position, args.league_size)
            print("="*80)
            print("📝 DRAFT RECOMMENDER PROMPT")
            print("="*80)
            print(prompt)
            print("="*80)
            return
        
        # Generate recommendations
        recommendations = recommender.generate_comprehensive_draft_plan(
            top_n=args.top_n,
            pick_position=args.pick_position,
            league_size=args.league_size
        )
        
        # Print recommendations
        print("\n" + "="*80)
        print("🎯 DRAFT RECOMMENDATIONS")
        print("="*80)
        print(recommendations)
        print("="*80)
        
        # Save if requested
        if args.save:
            recommender.save_recommendations(recommendations, args.output_file)
        
        logger.info("Draft recommendation process completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in draft recommendation process: {e}")
        raise

if __name__ == "__main__":
    main() 
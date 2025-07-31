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
                'ceiling_potential': 0.5
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
    
    def create_draft_analysis_prompt(self, top_players: pd.DataFrame, draft_rounds: int = 15) -> str:
        """Create a comprehensive prompt for draft analysis"""
        
        # Create player data for the prompt
        player_data = []
        for _, player in top_players.iterrows():
            player_info = {
                'name': player['name'],
                'position': player['position'],
                'team': player['team'],
                'vorp_score': round(player['vorp_score'], 2),
                'total_score': round(player['total_score'], 1),
                'tier': player['tier'],
                'position_rank': int(player['position_rank']),
                'consistency': round(player.get('consistency_score', 0.5), 2),
                'ceiling': round(player.get('ceiling_potential', 0.5), 2),
                'age': int(player.get('age', 0)),
                'projected_2025_pts': round(player.get('projected_2025_pts', 0), 1),
                'flags': player.get('flags', [])
            }
            player_data.append(player_info)
        
        # Create position scarcity analysis
        position_counts = top_players['position'].value_counts()
        scarcity_analysis = {}
        for pos in ['QB', 'RB', 'WR', 'TE']:
            count = position_counts.get(pos, 0)
            if count <= 3:
                scarcity = "HIGH - Very few elite options"
            elif count <= 6:
                scarcity = "MEDIUM - Some good options available"
            else:
                scarcity = "LOW - Many good options available"
            scarcity_analysis[pos] = scarcity

        league_size = 7
        draft_pick = 4
        
        prompt = f"""
        you are an expert fantasy‑football draft strategist.

        ### draft context
        - league size: {league_size} teams, snake draft
        - your draft position: {draft_pick} (use this to keep recommendations realistic)
        - rounds to plan: {draft_rounds}
        - roster: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX
        - scoring: full‑PPR
        - objective: maximize total team VORP while balancing positional scarcity and risk.

        ### data you have
        **position scarcity analysis**
        {json.dumps(scarcity_analysis, indent=2)}

        **top players by VORP**
        {json.dumps(player_data, indent=2)}

        ### deliverables
        1. **round‑by‑round plan for the first 3 rounds** (two fallback options per pick):
        - show “primary target” + “fallback if gone”
        - explain *why* (VORP edge, scarcity, risk, team construction).
        2. **call out positional drop‑offs** (e.g., “after TE2 there’s a 6‑point VORP cliff”).
        3. **best available board for rounds 4‑6**:
        - list 15 players with short reasoning + ADP range to prove they’re gettable.
        4. **draft strategy cheatsheet** at the end:
        - bullet points on roster balance, when to pivot, bye‑week awareness, etc.

        ### response format
        ## round 1‑3 draft roadmap

        ### round 1 (pick {draft_pick})
        **primary:** <name> – <pos> – <team> (VORP X | ADP Y)
        - why & scarcity

        **fallbacks if primary gone:**
        1. <name> – <pos> – VORP / ADP – 1‑sentence reason
        2. <name> – <pos> – VORP / ADP – 1‑sentence reason

        ### round 2
        <same structure>

        ### round 3
        <same structure>

        ## best available (rounds 4‑6)
        | rank | player | pos | team | VORP | ADP | note |
        |------|--------|-----|------|------|-----|------|
        | 1    | …      |     |      |      |     |      |
        … (15 rows)

        ## draft strategy cheatsheet
        - ♦ key scarcity points
        - ♦ when to grab QB if you passed early
        - ♦ injury volatility considerations
        - ♦ bye‑week stacking tips
        """

        
        return prompt
    
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
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=120)
            
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
    
    def generate_draft_recommendations(self, top_n: int = 50, draft_rounds: int = 15) -> str:
        """Generate comprehensive draft recommendations"""
        try:
            logger.info("Starting draft recommendation generation...")
            
            # Load ranking data
            df = self.load_ranking_data()
            
            # Get top VORP players
            top_players = self.get_top_vorp_players(df, top_n)
            
            # Print summary of players being analyzed
            self.print_player_summary(top_players)
            
            # Create analysis prompt
            prompt = self.create_draft_analysis_prompt(top_players, draft_rounds)
            
            # Get LLM analysis
            logger.info("Requesting draft analysis from Ollama...")
            recommendations = self.query_ollama(prompt)
            
            # Check if Ollama failed and provide fallback
            if recommendations.startswith("Error:"):
                logger.warning("Ollama connection failed, generating fallback recommendations...")
                recommendations = self.generate_fallback_recommendations(top_players, draft_rounds)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating draft recommendations: {e}")
            return f"Error generating recommendations: {str(e)}"
    
    def generate_fallback_recommendations(self, top_players: pd.DataFrame, draft_rounds: int = 15) -> str:
        """Generate fallback recommendations when Ollama is not available"""
        try:
            recommendations = []
            recommendations.append("## FALLBACK DRAFT RECOMMENDATIONS")
            recommendations.append("(Generated without LLM analysis - Ollama unavailable)")
            recommendations.append("")
            
            # Round 1-3 recommendations based on VORP
            recommendations.append("## ROUND 1-3 DRAFT ROADMAP")
            recommendations.append("")
            
            # Get top players by position for each round
            for round_num in [1, 2, 3]:
                recommendations.append(f"### ROUND {round_num}")
                
                # Get best available players for this round
                if round_num == 1:
                    # Top 3 VORP players
                    round_players = top_players.head(3)
                elif round_num == 2:
                    # Next 3 VORP players
                    round_players = top_players.iloc[3:6]
                else:
                    # Next 3 VORP players
                    round_players = top_players.iloc[6:9]
                
                for i, (_, player) in enumerate(round_players.iterrows(), 1):
                    recommendations.append(f"**Option {i}:** {player['name']} - {player['position']} - {player['team']}")
                    recommendations.append(f"  - VORP: {player['vorp_score']:.1f} | Score: {player['total_score']:.1f}")
                    recommendations.append(f"  - Tier: {player['tier']} | Age: {int(player['age'])}")
                    if player.get('flags'):
                        recommendations.append(f"  - Flags: {', '.join(player['flags'])}")
                    recommendations.append("")
            
            # Best available board
            recommendations.append("## BEST AVAILABLE (ROUNDS 4-6)")
            recommendations.append("| Rank | Player | Pos | Team | VORP | Score | Tier |")
            recommendations.append("|------|--------|-----|------|------|-------|------|")
            
            # Show next 15 players
            for i, (_, player) in enumerate(top_players.iloc[9:24].iterrows(), 1):
                recommendations.append(f"| {i} | {player['name']} | {player['position']} | {player['team']} | "
                                    f"{player['vorp_score']:.1f} | {player['total_score']:.1f} | {player['tier']} |")
            
            recommendations.append("")
            
            # Strategy tips
            recommendations.append("## DRAFT STRATEGY TIPS")
            recommendations.append("- ♦ Prioritize VORP over ADP - higher VORP = better value")
            recommendations.append("- ♦ RB scarcity is real - don't wait too long for RB2")
            recommendations.append("- ♦ WR depth allows for patience in middle rounds")
            recommendations.append("- ♦ QB can wait until rounds 6-8 in most cases")
            recommendations.append("- ♦ TE has steep drop-off after top 3-4 options")
            recommendations.append("- ♦ Consider age and injury risk for older players")
            recommendations.append("- ♦ Rookies have upside but also risk")
            recommendations.append("- ♦ Monitor bye weeks to avoid conflicts")
            
            return "\n".join(recommendations)
            
        except Exception as e:
            logger.error(f"Error generating fallback recommendations: {e}")
            return "Error generating fallback recommendations"
    
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
    parser.add_argument('--draft-rounds', type=int, default=15,
                       help='Number of draft rounds to consider (default: 15)')
    parser.add_argument('--ollama-url', type=str, default=None,
                       help='Ollama API URL (default: uses OLLAMA_HOST env var or 127.0.0.1)')
    parser.add_argument('--model', type=str, default='deepseek-r1',
                       help='Ollama model to use (default: deepseek-r1)')
    parser.add_argument('--save', action='store_true',
                       help='Save recommendations to file')
    parser.add_argument('--output-file', type=str, default=None,
                       help='Output filename (default: auto-generated)')
    
    args = parser.parse_args()
    
    try:
        # Initialize recommender
        recommender = DraftRecommender(
            ollama_url=args.ollama_url,
            model=args.model
        )
        
        # Generate recommendations
        recommendations = recommender.generate_draft_recommendations(
            top_n=args.top_n,
            draft_rounds=args.draft_rounds
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
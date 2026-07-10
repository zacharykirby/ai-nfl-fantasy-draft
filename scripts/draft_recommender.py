#!/usr/bin/env python3
"""
NFL Fantasy Draft Recommendation System
Uses OpenRouter models to analyze top VORP-ranked players and suggest optimal draft pick ordering

This script:
1. Loads the ranking data and VORP scores
2. Identifies top players by VORP across all positions
3. Sends data to OpenRouter for strategic analysis
4. Outputs draft recommendations with reasoning
"""

import pandas as pd
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import sys
from datetime import datetime

from llm_client import OpenRouterClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

class DraftRecommender:
    """Draft recommendation system using OpenRouter model analysis"""
    
    def __init__(self, model: str = None, allow_stale_rankings: bool = False):
        self.client = OpenRouterClient(model=model)
        self.model = self.client.model
        self.allow_stale_rankings = allow_stale_rankings
        self.rankings_dir = Path("outputs")
        self.rankings_metadata: Dict[str, object] = {}
        
    def load_ranking_data(self) -> pd.DataFrame:
        """Load the latest ranking data from player_rankings.json"""
        try:
            # Load the player rankings JSON file
            rankings_file = self.rankings_dir / "player_rankings.json"
            if not rankings_file.exists():
                raise FileNotFoundError(f"Ranking data not found at {rankings_file}")
            
            with open(rankings_file, 'r') as f:
                rankings_payload = json.load(f)

            rankings_data, metadata = self._normalize_rankings_payload(rankings_payload)
            self.rankings_metadata = metadata
            self._validate_rankings_freshness(rankings_file, metadata)
            
            # Convert JSON data to DataFrame
            df = pd.DataFrame(rankings_data)

            try:
                legacy_projection_year = int(metadata.get('target_season')) - 1
            except (TypeError, ValueError):
                legacy_projection_year = 2025
            legacy_projection_col = f"projected_{legacy_projection_year}_pts"
            if 'projected_fantasy_points' not in df.columns and legacy_projection_col in df.columns:
                df['projected_fantasy_points'] = df[legacy_projection_col]
            
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
                'projected_fantasy_points': 0.0,
                'projection_rank': 999,
                'projection_tier': 99,
                'raw_score': 0.0,
                'consistency_score': 0.5,
                'ceiling_potential': 0.5,
                'bye_week': 'N/A'
            }
            
            for col, default_val in required_columns.items():
                if col not in df.columns:
                    df[col] = default_val
            
            # Convert numeric columns
            numeric_columns = ['total_score', 'vorp_score', 'age', 'projected_fantasy_points', 'projection_rank',
                               'projection_tier', 'raw_score', 'consistency_score', 'ceiling_potential']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            logger.info(f"Loaded {len(df)} ranked players from {rankings_file}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading ranking data: {e}")
            raise

    def _normalize_rankings_payload(self, payload: object) -> Tuple[List[Dict], Dict[str, object]]:
        """Support both legacy list exports and metadata-wrapped ranking exports."""
        if isinstance(payload, list):
            return payload, {}
        if isinstance(payload, dict):
            rankings = payload.get("rankings", [])
            metadata = payload.get("metadata", {})
            if isinstance(rankings, list) and isinstance(metadata, dict):
                return rankings, metadata
        raise ValueError("Ranking file must be a list or an object with rankings/metadata")

    def _validate_rankings_freshness(self, rankings_file: Path, metadata: Dict[str, object]) -> None:
        """Avoid using stale rankings as if they were current draft advice."""
        current_year = datetime.now().year
        target_season = metadata.get("target_season")
        generated_at = metadata.get("generated_at")
        projection_source = metadata.get("projection_source")

        stale_reasons = []
        if not target_season:
            stale_reasons.append("missing target_season metadata")
        else:
            try:
                if int(target_season) < current_year:
                    stale_reasons.append(f"target season {target_season} is older than {current_year}")
            except (TypeError, ValueError):
                stale_reasons.append(f"invalid target_season metadata: {target_season}")

        if not generated_at:
            stale_reasons.append("missing generated_at metadata")
        if projection_source == "historical_fantasy_points_fallback":
            stale_reasons.append("rankings were generated without target-season projections")

        if stale_reasons and not self.allow_stale_rankings:
            reason_text = "; ".join(stale_reasons)
            raise ValueError(
                f"{rankings_file} looks stale ({reason_text}). "
                "Refresh data/rankings first or pass --allow-stale-rankings for inspection only."
            )
        if stale_reasons:
            logger.warning("Using potentially stale rankings: %s", "; ".join(stale_reasons))
    
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

    def prepare_draft_board(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build a position-aware draft board from ranking output."""
        board = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
        board = board[board['projected_fantasy_points'] > 0].copy()
        board['projection_rank'] = pd.to_numeric(board['projection_rank'], errors='coerce').fillna(999)
        board['projection_tier'] = pd.to_numeric(board['projection_tier'], errors='coerce').fillna(99)
        board['position_rank'] = board.groupby('position')['projection_rank'].rank(method='first', ascending=True)
        board = board.sort_values(['projection_rank', 'vorp_score'], ascending=[True, False]).reset_index(drop=True)
        return board

    def _format_player(self, player: Optional[pd.Series]) -> str:
        """Format one player line for draft output."""
        if player is None:
            return "No viable option in current board"
        rank = int(player.get('projection_rank', 999))
        rank_text = f"ADP/rank {rank}" if rank < 999 else "rank N/A"
        return (
            f"{player['name']} - {player['position']} - {player['team']} "
            f"(VORP: {player['vorp_score']:.1f} | Proj: {player['projected_fantasy_points']:.1f} | "
            f"{rank_text} | Bye: Week {player.get('bye_week', 'N/A')})"
        )

    def _pool_for_pick(
        self,
        board: pd.DataFrame,
        overall_pick: int,
        league_size: int,
        selected_names: set,
        pool: str = "likely",
    ) -> pd.DataFrame:
        """Return a realistic availability pool for a pick based on projection rank."""
        available = board[~board['name'].isin(selected_names)].copy()
        if available.empty:
            return available

        rank = pd.to_numeric(available['projection_rank'], errors='coerce').fillna(999)
        likely_floor = max(1, overall_pick - 1)
        next_pick = overall_pick + league_size

        if pool == "likely":
            return available[rank >= likely_floor].copy()
        if pool == "fallers":
            faller_floor = max(1, overall_pick - league_size)
            return available[(rank >= faller_floor) & (rank < likely_floor)].copy()
        if pool == "reach":
            reach_floor = next_pick + 1
            return available[rank >= reach_floor].copy()
        return available

    def _top_candidates(
        self,
        board: pd.DataFrame,
        overall_pick: int,
        league_size: int,
        selected_names: set,
        pool: str = "likely",
        limit: int = 5,
        position: Optional[str] = None,
    ) -> pd.DataFrame:
        """Return top candidates for a pick, optionally constrained to one position."""
        candidates = self._pool_for_pick(board, overall_pick, league_size, selected_names, pool=pool)
        if position:
            candidates = candidates[candidates['position'] == position].copy()
        if candidates.empty:
            return candidates

        if pool == "fallers":
            candidates = candidates.sort_values(['projection_rank', 'vorp_score'], ascending=[True, False])
        elif pool == "reach":
            candidates = candidates.sort_values(['vorp_score', 'projection_rank'], ascending=[False, True])
        else:
            candidates = candidates.sort_values(['projection_rank', 'vorp_score'], ascending=[True, False])
        return candidates.head(limit)

    def _candidate_for_position(
        self,
        board: pd.DataFrame,
        position: str,
        overall_pick: int,
        league_size: int,
        selected_names: set,
    ) -> Optional[pd.Series]:
        """Pick the best likely-available player at a position."""
        likely = self._top_candidates(
            board, overall_pick, league_size, selected_names, pool="likely", limit=1, position=position
        )
        if not likely.empty:
            return likely.iloc[0]

        reach = self._top_candidates(
            board, overall_pick, league_size, selected_names, pool="reach", limit=1, position=position
        )
        if not reach.empty:
            return reach.iloc[0]
        return None

    def _choose_primary_target(
        self,
        role_options: Dict[str, Optional[pd.Series]],
        roster_counts: Dict[str, int],
        round_num: int,
    ) -> Optional[pd.Series]:
        """Choose a practical primary target from the per-position options."""
        roster_targets = {'RB': 2, 'WR': 3, 'QB': 1, 'TE': 1}
        if round_num <= 2:
            eligible_positions = ['RB', 'WR', 'TE']
        elif round_num <= 4:
            eligible_positions = ['RB', 'WR', 'TE']
        elif round_num <= 6:
            eligible_positions = ['RB', 'WR', 'TE', 'QB']
        else:
            eligible_positions = ['RB', 'WR', 'QB', 'TE']

        needed = [
            pos for pos in eligible_positions
            if roster_counts.get(pos, 0) < roster_targets.get(pos, 0) and role_options.get(pos) is not None
        ]
        if not needed:
            needed = [pos for pos in eligible_positions if role_options.get(pos) is not None]
        if not needed:
            return None

        best_pos = min(
            needed,
            key=lambda pos: (
                float(role_options[pos].get('projection_rank', 999)),
                -float(role_options[pos].get('vorp_score', 0)),
            ),
        )
        return role_options[best_pos]

    def generate_local_draft_plan(self, board: pd.DataFrame, pick_position: int, league_size: int, rounds: int = 8) -> str:
        """Generate a fast, position-aware draft plan without an LLM call."""
        if pick_position < 1 or pick_position > league_size:
            raise ValueError(f"pick_position must be between 1 and league_size ({league_size})")

        snake_picks = self._calculate_snake_picks(pick_position, league_size, rounds=rounds)
        selected_names = set()
        roster_counts = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0}
        lines = [
            f"## POSITION-AWARE DRAFT PLAN - {league_size}-TEAM LEAGUE",
            f"**Draft Slot:** {pick_position} | **Your Overall Picks:** {', '.join(str(p) for p in snake_picks)}",
            "",
            "### Preferred Picks By Role",
        ]

        for position in ['QB', 'RB', 'WR', 'TE']:
            top = board[board['position'] == position].head(8)
            names = [self._format_player(player) for _, player in top.iterrows()]
            lines.append(f"**{position}:**")
            for item in names[:5]:
                lines.append(f"- {item}")
            lines.append("")

        lines.append("### Round Plan")
        for round_num, overall_pick in enumerate(snake_picks, 1):
            likely_targets = self._top_candidates(
                board, overall_pick, league_size, selected_names, pool="likely", limit=6
            )
            falling_values = self._top_candidates(
                board, overall_pick, league_size, selected_names, pool="fallers", limit=4
            )
            reach_values = self._top_candidates(
                board, overall_pick, league_size, selected_names, pool="reach", limit=4
            )
            role_options = {
                pos: self._candidate_for_position(board, pos, overall_pick, league_size, selected_names)
                for pos in ['RB', 'WR', 'QB', 'TE']
            }
            primary = self._choose_primary_target(role_options, roster_counts, round_num)
            if primary is not None:
                selected_names.add(primary['name'])
                roster_counts[primary['position']] = roster_counts.get(primary['position'], 0) + 1

            lines.append(f"**Round {round_num} - Overall Pick {overall_pick}**")
            lines.append(f"Primary Target: {self._format_player(primary)}")
            lines.append("Likely available board:")
            for _, player in likely_targets.iterrows():
                lines.append(f"- {self._format_player(player)}")
            if falling_values.empty:
                lines.append("Possible fallers: None projected this round")
            else:
                lines.append("Possible fallers if the room lets value slip:")
                for _, player in falling_values.iterrows():
                    lines.append(f"- {self._format_player(player)}")
            lines.append("Reach/watchlist options:")
            for _, player in reach_values.iterrows():
                lines.append(f"- {self._format_player(player)}")
            lines.append("Preferred by role:")
            for pos in ['RB', 'WR', 'QB', 'TE']:
                lines.append(f"- {pos}: {self._format_player(role_options[pos])}")
            lines.append(f"Roster after pick: QB {roster_counts['QB']}, RB {roster_counts['RB']}, WR {roster_counts['WR']}, TE {roster_counts['TE']}")
            lines.append("")

        lines.extend([
            "### Draft Notes",
            "- Availability is estimated from projection rank/ADP: likely targets start near your current overall pick.",
            "- Possible fallers are listed separately so early-round stars are not treated as the default available board.",
            "- Treat QB as a value pick in this league size unless an elite option reaches the likely/faller range.",
            "- Prioritize RB/WR starters early, then fill TE/QB when the positional value is clean.",
            "- Use the role rows during the draft: if the primary target is gone, pivot within the position that best fits your roster.",
        ])
        return "\n".join(lines)
    
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
        
        prompt = f"""Create a realistic fantasy football draft strategy for a {league_size}-team league, drafting from position {pick_position}.

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

    def _calculate_snake_picks(self, pick_position: int, league_size: int, rounds: int = 15) -> List[int]:
        """Calculate overall pick numbers for a given position in a snake draft."""
        picks = []
        for round_num in range(1, rounds + 1):
            if round_num % 2 == 1:  # Odd rounds (1, 3, 5, etc.)
                pick = ((round_num - 1) * league_size) + pick_position
            else:  # Even rounds (2, 4, 6, etc.)
                pick = (round_num * league_size) - pick_position + 1
            
            picks.append(pick)
        return picks

    def generate_comprehensive_draft_plan(self, top_n: int = 50, pick_position: int = 1, league_size: int = 8,
                                          use_ai: bool = False) -> str:
        """Generate a draft plan. Defaults to fast local recommendations."""
        try:
            logger.info(f"Generating comprehensive draft plan for {league_size}-team league, pick position {pick_position}...")
            
            # Load ranking data
            df = self.load_ranking_data()
            board = self.prepare_draft_board(df)

            if not use_ai:
                return self.generate_local_draft_plan(board, pick_position, league_size)
            
            # Get top VORP players
            top_players = self.get_top_vorp_players(board, top_n)
            
            # Print summary of players being analyzed
            self.print_player_summary(top_players)
            
            # Create comprehensive analysis prompt
            prompt = self.create_comprehensive_draft_plan(top_players, pick_position, league_size)
            
            # Get LLM analysis
            logger.info("Requesting comprehensive draft analysis from OpenRouter...")
            recommendations = self.query_model(prompt)
            
            # Check if the model failed and provide fallback
            if recommendations.startswith("Error:"):
                logger.warning("OpenRouter request failed, generating fallback recommendations...")
                recommendations = self.generate_local_draft_plan(board, pick_position, league_size)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating comprehensive draft plan: {e}")
            return f"Error generating draft plan: {str(e)}"

    def generate_fallback_comprehensive_plan(self, top_players: pd.DataFrame, pick_position: int, league_size: int) -> str:
        """Generate fallback comprehensive draft plan when OpenRouter is not available"""
        try:
            snake_picks = self._calculate_snake_picks(pick_position, league_size)
            
            recommendations = []
            recommendations.append(f"## COMPREHENSIVE DRAFT PLAN - {league_size}-TEAM LEAGUE")
            recommendations.append(f"**Draft Position:** {pick_position} | **Your Picks:** {snake_picks}")
            recommendations.append("(Generated without LLM analysis - OpenRouter unavailable)")
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

                primary_idx = min((round_num - 1) * 3, len(top_players) - 1)
                primary = top_players.iloc[primary_idx]
                fallback_players = top_players.iloc[primary_idx + 1:min(primary_idx + 3, len(top_players))]
                
                recommendations.append(f"**Primary Target:** {primary['name']} - {primary['position']} - {primary['team']}")
                recommendations.append(f"  - VORP: {primary['vorp_score']:.1f} | Bye: Week {primary.get('bye_week', 'N/A')}")
                recommendations.append(f"  - Reasoning: Best available VORP value")
                recommendations.append("")
                
                recommendations.append("**Fallback Options:**")
                if fallback_players.empty:
                    recommendations.append("No additional options in the selected top-player pool.")
                else:
                    for option_num, (_, fallback) in enumerate(fallback_players.iterrows(), 1):
                        recommendations.append(
                            f"{option_num}. {fallback['name']} - {fallback['position']} - {fallback['team']} "
                            f"(VORP: {fallback['vorp_score']:.1f} | Bye: {fallback.get('bye_week', 'N/A')})"
                        )
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
    
    def query_model(self, prompt: str) -> str:
        """Send prompt to OpenRouter and get response."""
        logger.info(f"Sending draft analysis request to OpenRouter ({self.model})...")
        return self.client.chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are a practical fantasy football draft analyst. Be concise, current, and explicit about uncertainty.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            timeout=120,
        )
    
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
                f.write("Generated by OpenRouter model analysis\n")
                f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Model: {self.model}\n")
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
    parser.add_argument('--model', type=str, default=None,
                       help='OpenRouter model slug to use (default: OPENROUTER_MODEL or openai/gpt-4o-mini)')
    parser.add_argument('--allow-stale-rankings', action='store_true',
                       help='Allow legacy/stale ranking files for inspection only')
    parser.add_argument('--save', action='store_true',
                       help='Save recommendations to file')
    parser.add_argument('--output-file', type=str, default=None,
                       help='Output filename (default: auto-generated)')
    parser.add_argument('--print-prompt', action='store_true',
                       help='Print only the prompt and exit (for copy/paste)')
    parser.add_argument('--use-ai', action='store_true',
                       help='Ask OpenRouter to write the draft analysis after building the local board')
    
    args = parser.parse_args()
    
    try:
        # Initialize recommender
        recommender = DraftRecommender(
            model=args.model,
            allow_stale_rankings=args.allow_stale_rankings
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
            league_size=args.league_size,
            use_ai=args.use_ai
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

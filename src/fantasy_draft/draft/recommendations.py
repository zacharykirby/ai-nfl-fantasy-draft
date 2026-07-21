#!/usr/bin/env python3
"""Deterministic, explainable recommendations for an active draft session."""

import math
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from fantasy_draft.draft.session import BOARD_POSITIONS, DraftSession, next_pick_for_team


RECOMMENDATION_SCHEMA_VERSION = "1.0"
MODES = ("safe", "balanced", "upside")
DEFAULT_STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}


def tier_number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        text = str(value or "")
        digits = "".join(char for char in text if char.isdigit())
        return int(digits) if digits else 99


def survival_probability(adp: Any, next_pick: Optional[int]) -> Optional[float]:
    """Estimate survival from market ADP with a deliberately simple logistic curve."""
    if next_pick is None or adp in (None, ""):
        return None
    try:
        market_pick = float(adp)
    except (TypeError, ValueError):
        return None
    probability = 1.0 / (1.0 + math.exp((float(next_pick) - market_pick) / 6.0))
    return round(max(0.01, min(0.99, probability)), 2)


class DraftRecommendationEngine:
    def __init__(self, session: DraftSession):
        self.session = session

    def roster_counts(self) -> Dict[str, int]:
        counts = Counter(player["position"] for player in self.session.roster())
        return {position: int(counts.get(position, 0)) for position in BOARD_POSITIONS}

    def roster_needs(self) -> Dict[str, Dict[str, Any]]:
        starters = dict(DEFAULT_STARTERS)
        starters.update(self.session.payload.get("league", {}).get("starters", {}))
        counts = self.roster_counts()
        needs: Dict[str, Dict[str, Any]] = {}
        for position in BOARD_POSITIONS:
            target = int(starters.get(position, 0) or 0)
            needs[position] = {
                "rostered": counts[position],
                "base_starters": target,
                "open_base_slots": max(0, target - counts[position]),
                "needed": counts[position] < target,
            }

        flex_slots = int(starters.get("FLEX", 0) or 0)
        base_filled = sum(min(counts[pos], int(starters.get(pos, 0) or 0)) for pos in ("RB", "WR", "TE"))
        base_targets = sum(int(starters.get(pos, 0) or 0) for pos in ("RB", "WR", "TE"))
        surplus = sum(max(0, counts[pos] - int(starters.get(pos, 0) or 0)) for pos in ("RB", "WR", "TE"))
        flex_open = max(0, flex_slots - surplus) if base_filled >= base_targets else flex_slots
        for position in ("RB", "WR", "TE"):
            needs[position]["flex_eligible"] = True
            needs[position]["open_flex_slots"] = flex_open
        needs["QB"]["flex_eligible"] = False
        needs["QB"]["open_flex_slots"] = 0
        return needs

    def tier_state(self) -> Dict[str, Dict[str, Any]]:
        state = {}
        for position in BOARD_POSITIONS:
            available = self.session.available_players(position)
            if not available:
                state[position] = {
                    "best_tier": None,
                    "remaining_in_best_tier": 0,
                    "next_tier": None,
                    "tier_drop_imminent": False,
                }
                continue
            best_tier = min(tier_number(player.get("tier")) for player in available)
            in_tier = [player for player in available if tier_number(player.get("tier")) == best_tier]
            worse_tiers = sorted({
                tier_number(player.get("tier")) for player in available
                if tier_number(player.get("tier")) > best_tier
            })
            state[position] = {
                "best_tier": best_tier,
                "remaining_in_best_tier": len(in_tier),
                "next_tier": worse_tiers[0] if worse_tiers else None,
                "tier_drop_imminent": len(in_tier) <= 2 and bool(worse_tiers),
            }
        return state

    def position_run(self, window: int = 6, threshold: int = 3) -> Dict[str, Any]:
        recent = self.session.active_selections()[-window:]
        counts = Counter(event.get("position") for event in recent)
        active_positions = sorted(
            position for position, count in counts.items()
            if position in BOARD_POSITIONS and count >= threshold
        )
        return {
            "window": window,
            "threshold": threshold,
            "recent_picks": len(recent),
            "counts": {position: int(counts.get(position, 0)) for position in BOARD_POSITIONS},
            "active": bool(active_positions),
            "positions": active_positions,
        }

    def _candidate_score(
        self,
        player: Dict[str, Any],
        mode: str,
        needs: Dict[str, Dict[str, Any]],
        tiers: Dict[str, Dict[str, Any]],
        run: Dict[str, Any],
        next_user_pick: Optional[int],
    ) -> Tuple[float, Dict[str, float], List[str]]:
        position = player["position"]
        overall_rank = int(player.get("overall_rank") or 999)
        position_rank = int(player.get("position_rank") or 999)
        vorp = float(player.get("vorp") or 0)
        tier = tier_number(player.get("tier"))
        flags = {str(flag).casefold() for flag in player.get("flags", [])}
        risk = player.get("risk", {})

        weights = {
            "safe": {"board": 0.48, "vorp": 0.28, "tier": 1.0},
            "balanced": {"board": 0.42, "vorp": 0.36, "tier": 1.0},
            "upside": {"board": 0.35, "vorp": 0.48, "tier": 0.9},
        }[mode]
        components = {
            "board_value": max(0.0, 220.0 - overall_rank) * weights["board"],
            "position_value": max(0.0, 70.0 - position_rank) * 0.12,
            "vorp_value": vorp * weights["vorp"],
            "tier_value": max(0.0, 6.0 - tier) * 8.0 * weights["tier"],
            "roster_need": 18.0 if needs[position]["needed"] else 0.0,
            "tier_scarcity": 12.0 if tiers[position]["tier_drop_imminent"] and tier == tiers[position]["best_tier"] else 0.0,
            "position_run": 4.0 if position in run["positions"] else 0.0,
            "source_confidence": -10.0 if player.get("projection_method") == "adp_estimate" else 0.0,
            "risk_adjustment": 0.0,
            "upside_adjustment": 0.0,
        }

        is_injured = bool(risk.get("injury_flag"))
        risk_level = str(risk.get("level", "unknown")).casefold()
        if mode == "safe":
            if is_injured:
                components["risk_adjustment"] -= 28.0
            if risk_level == "high" or "age risk" in flags:
                components["risk_adjustment"] -= 12.0
            if "high projection" in flags:
                components["risk_adjustment"] += 5.0
        elif mode == "upside":
            if "high upside" in flags:
                components["upside_adjustment"] += 14.0
            if "elite tier" in flags:
                components["upside_adjustment"] += 5.0
            if is_injured:
                components["risk_adjustment"] -= 10.0
        else:
            if is_injured:
                components["risk_adjustment"] -= 18.0
            if "high upside" in flags:
                components["upside_adjustment"] += 5.0

        survival = survival_probability(player.get("adp"), next_user_pick)
        if survival is not None and survival <= 0.25:
            components["will_not_survive"] = 9.0

        reasons = [
            "{}{} on the position board".format(position, position_rank),
            "Tier {} with {:.1f} VORP".format(tier, vorp),
        ]
        if needs[position]["needed"]:
            reasons.append("fills an open {} starter slot".format(position))
        if components["tier_scarcity"]:
            reasons.append("{} player(s) remain in the best {} tier".format(
                tiers[position]["remaining_in_best_tier"], position
            ))
        if position in run["positions"]:
            reasons.append("{} is in a recent position run".format(position))
        if survival is not None and survival <= 0.25:
            reasons.append("estimated {:.0%} chance to survive to your next pick".format(survival))
        if player.get("projection_method") == "adp_estimate":
            reasons.append("projection is an ADP estimate, reducing confidence")
        if mode == "upside" and "high upside" in flags:
            reasons.append("board flags high upside")
        if is_injured:
            reasons.append("active injury flag lowers confidence")

        return round(sum(components.values()), 3), components, reasons

    def recommend(self, mode: str = "balanced", alternatives: int = 4) -> Dict[str, Any]:
        if mode not in MODES:
            raise ValueError("mode must be safe, balanced, or upside")
        if self.session.current_team is None:
            raise ValueError("Draft is complete")

        needs = self.roster_needs()
        tiers = self.tier_state()
        run = self.position_run()
        next_user_pick = next_pick_for_team(
            self.session.current_pick + 1,
            self.session.user_team,
            self.session.league_size,
            self.session.rounds,
        )
        candidates = self.session.available_players()[:40]
        scored = []
        for player in candidates:
            score, components, reasons = self._candidate_score(
                player, mode, needs, tiers, run, next_user_pick
            )
            scored.append({
                "player_id": player["player_id"],
                "player": player["player"],
                "position": player["position"],
                "team": player.get("team"),
                "position_rank": player.get("position_rank"),
                "overall_rank": player.get("overall_rank"),
                "tier": tier_number(player.get("tier")),
                "projected_points": player.get("projected_points"),
                "vorp": player.get("vorp"),
                "adp": player.get("adp"),
                "bye_week": player.get("bye_week"),
                "survival_to_next_pick": survival_probability(player.get("adp"), next_user_pick),
                "recommendation_score": score,
                "score_components": {key: round(value, 3) for key, value in components.items()},
                "reasons": reasons,
            })
        scored.sort(key=lambda item: (-item["recommendation_score"], item["overall_rank"] or 999))
        if not scored:
            raise ValueError("No players remain available")

        primary = scored[0]
        runner_ups = scored[1:1 + max(0, alternatives)]
        confidence_gap = primary["recommendation_score"] - (runner_ups[0]["recommendation_score"] if runner_ups else 0)
        confidence = round(max(0.5, min(0.95, 0.62 + (confidence_gap / 100.0))), 2)
        return {
            "schema_version": RECOMMENDATION_SCHEMA_VERSION,
            "mode": mode,
            "generated_for": {
                "current_pick": self.session.current_pick,
                "current_team": self.session.current_team,
                "user_team": self.session.user_team,
                "is_user_pick": self.session.current_team == self.session.user_team,
                "next_user_pick": next_user_pick,
            },
            "primary": primary,
            "alternatives": runner_ups,
            "confidence": confidence,
            "signals": {
                "roster_needs": needs,
                "tiers": tiers,
                "position_run": run,
            },
        }

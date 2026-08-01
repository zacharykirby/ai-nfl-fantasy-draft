#!/usr/bin/env python3
"""Deterministic, explainable recommendations for an active draft session."""

import math
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from fantasy_draft.draft.session import BOARD_POSITIONS, DraftSession, next_pick_for_team


RECOMMENDATION_SCHEMA_VERSION = "1.0"
MODES = ("safe", "balanced", "upside")
DEFAULT_STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}
FLEX_POSITIONS = ("RB", "WR", "TE")


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


def wait_status(probability: Optional[float]) -> str:
    """Turn a disclosed survival heuristic into restrained wait language."""
    if probability is None:
        return "unknown"
    if probability >= 0.70:
        return "yes"
    if probability >= 0.45:
        return "probably"
    if probability >= 0.20:
        return "risky"
    return "no"


class DraftRecommendationEngine:
    def __init__(self, session: DraftSession):
        self.session = session
        self._replacement_cache: Optional[Dict[str, Dict[str, Any]]] = None

    def roster_counts(self) -> Dict[str, int]:
        counts = Counter(player["position"] for player in self.session.roster())
        return {position: int(counts.get(position, 0)) for position in BOARD_POSITIONS}

    def league_starters(self) -> Dict[str, int]:
        starters = dict(DEFAULT_STARTERS)
        starters.update(self.session.payload.get("league", {}).get("starters", {}))
        return {
            position: max(0, int(starters.get(position, 0) or 0))
            for position in (*BOARD_POSITIONS, "FLEX")
        }

    def draft_progress(self) -> float:
        total = max(1, self.session.league_size * self.session.rounds)
        return max(0.0, min(1.0, (self.session.current_pick - 1) / total))

    @staticmethod
    def _projection(player: Dict[str, Any]) -> float:
        try:
            return float(player.get("projected_points") or 0)
        except (TypeError, ValueError):
            return 0.0

    def replacement_levels(self) -> Dict[str, Dict[str, Any]]:
        """Derive replacement ranks from this league's starters and FLEX demand."""
        if self._replacement_cache is not None:
            return self._replacement_cache
        starters = self.league_starters()
        league_size = self.session.league_size
        pools = {
            position: sorted(
                (
                    player
                    for player in self.session.payload["board"]["players"]
                    if player.get("position") == position
                ),
                key=lambda player: (
                    -self._projection(player),
                    int(player.get("position_rank") or 999),
                ),
            )
            for position in BOARD_POSITIONS
        }
        base_demand = {
            position: league_size * starters[position]
            for position in BOARD_POSITIONS
        }
        flex_candidates = []
        for position in FLEX_POSITIONS:
            for player in pools[position][base_demand[position]:]:
                flex_candidates.append(player)
        flex_candidates.sort(key=lambda player: (
            -self._projection(player),
            int(player.get("overall_rank") or 999),
        ))
        flex_allocations = Counter(
            player["position"]
            for player in flex_candidates[:league_size * starters["FLEX"]]
        )

        levels: Dict[str, Dict[str, Any]] = {}
        for position in BOARD_POSITIONS:
            pool = pools[position]
            demand = base_demand[position] + int(flex_allocations.get(position, 0))
            if not pool:
                levels[position] = {
                    "replacement_rank": None,
                    "baseline_points": 0.0,
                    "base_starter_demand": base_demand[position],
                    "flex_demand": int(flex_allocations.get(position, 0)),
                    "source": "league_starters_and_projections",
                }
                continue
            replacement_rank = min(len(pool), max(1, demand + 1))
            index = replacement_rank - 1
            window = pool[max(0, index - 1):min(len(pool), index + 2)]
            projections = [self._projection(player) for player in window]
            baseline = sum(projections) / len(projections) if projections else 0.0
            levels[position] = {
                "replacement_rank": replacement_rank,
                "baseline_points": round(baseline, 3),
                "base_starter_demand": base_demand[position],
                "flex_demand": int(flex_allocations.get(position, 0)),
                "source": "league_starters_and_projections",
            }
        self._replacement_cache = levels
        return levels

    def roster_needs(self) -> Dict[str, Dict[str, Any]]:
        starters = self.league_starters()
        counts = self.roster_counts()
        progress = self.draft_progress()
        bench_size = max(0, int(self.session.payload.get("league", {}).get("bench_size") or 0))
        backup_targets = {
            "QB": 1 if starters["QB"] and bench_size >= 5 else 0,
            "TE": 1 if starters["TE"] and bench_size >= 6 else 0,
            "RB": max(1, math.ceil(bench_size * 0.5)) if starters["RB"] else 0,
            "WR": max(1, bench_size // 2) if starters["WR"] else 0,
        }
        needs: Dict[str, Dict[str, Any]] = {}
        for position in BOARD_POSITIONS:
            target = int(starters.get(position, 0) or 0)
            open_base = max(0, target - counts[position])
            depth_target = target + backup_targets[position]
            depth_open = max(0, depth_target - counts[position])
            excess = max(0, counts[position] - depth_target)
            if open_base:
                need_level = "urgent" if progress >= 0.70 else (
                    "priority" if progress >= 0.35 else "open"
                )
                score_adjustment = 8.0 + (16.0 * progress)
            elif excess:
                need_level = "excess"
                score_adjustment = -(10.0 + (15.0 * progress))
            elif depth_open:
                need_level = "depth"
                score_adjustment = 2.0 + (3.0 * progress)
            else:
                need_level = "at_capacity"
                score_adjustment = -(6.0 + (12.0 * progress))
            needs[position] = {
                "rostered": counts[position],
                "base_starters": target,
                "open_base_slots": open_base,
                "needed": counts[position] < target,
                "need_level": need_level,
                "depth_target": depth_target,
                "depth_open": depth_open,
                "excess": excess,
                "score_adjustment": round(score_adjustment, 3),
            }

        flex_slots = int(starters.get("FLEX", 0) or 0)
        surplus = sum(max(0, counts[pos] - starters[pos]) for pos in FLEX_POSITIONS)
        flex_open = max(0, flex_slots - surplus)
        for position in FLEX_POSITIONS:
            needs[position]["flex_eligible"] = True
            needs[position]["open_flex_slots"] = flex_open
            if flex_open and not needs[position]["open_base_slots"]:
                needs[position]["need_level"] = "flex"
                needs[position]["score_adjustment"] = round(
                    5.0 + (8.0 * progress), 3
                )
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

    def tier_survival_probability(
        self,
        position: str,
        tier: int,
        next_pick: Optional[int],
    ) -> Optional[float]:
        probabilities = [
            survival_probability(player.get("adp"), next_pick)
            for player in self.session.available_players(position)
            if tier_number(player.get("tier")) == tier
        ]
        known = [probability for probability in probabilities if probability is not None]
        if not known:
            return None
        none_survive = math.prod(1.0 - probability for probability in known)
        return round(max(0.01, min(0.99, 1.0 - none_survive)), 2)

    def candidate_caveats(
        self,
        player: Dict[str, Any],
        needs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[str]:
        needs = needs or self.roster_needs()
        caveats = []
        bye_week = player.get("bye_week")
        if bye_week in (None, ""):
            caveats.append("Bye week is unknown; roster overlap cannot be assessed.")
        else:
            overlapping = [
                rostered for rostered in self.session.roster()
                if rostered.get("bye_week") == bye_week
            ]
            if overlapping:
                names = ", ".join(item["player"] for item in overlapping[:2])
                caveats.append("Bye {} overlaps with {}.".format(bye_week, names))
        position_need = needs[player["position"]]
        if position_need["need_level"] in {"at_capacity", "excess"}:
            caveats.append(
                "Another {} would exceed the current roster-balance target.".format(
                    player["position"]
                )
            )
        return caveats[:3]

    def roster_balance_warnings(
        self,
        needs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        needs = needs or self.roster_needs()
        progress = self.draft_progress()
        warnings = []
        open_positions = [
            position for position in BOARD_POSITIONS
            if needs[position]["open_base_slots"]
        ]
        if open_positions and progress >= 0.65:
            warnings.append({
                "code": "open_starter_slots",
                "severity": "high" if progress >= 0.85 else "warning",
                "positions": open_positions,
                "message": "Open starter slots remain at {} late in the draft.".format(
                    "/".join(open_positions)
                ),
            })
        for position in ("QB", "TE"):
            if needs[position]["excess"]:
                warnings.append({
                    "code": "position_overload",
                    "severity": "warning",
                    "positions": [position],
                    "message": "{} depth exceeds the configured roster-balance target.".format(
                        position
                    ),
                })
        byes: Dict[Any, List[Dict[str, Any]]] = {}
        for player in self.session.roster():
            bye_week = player.get("bye_week")
            if bye_week not in (None, ""):
                byes.setdefault(bye_week, []).append(player)
        for bye_week, players in sorted(byes.items(), key=lambda item: item[0]):
            positions = Counter(player["position"] for player in players)
            if len(players) >= 3 or any(count >= 2 for count in positions.values()):
                warnings.append({
                    "code": "bye_cluster",
                    "severity": "caveat",
                    "positions": sorted(positions),
                    "message": "{} rostered players share bye {}.".format(
                        len(players), bye_week
                    ),
                })
        return warnings[:6]

    def wait_assessment(
        self,
        player: Dict[str, Any],
        next_pick: Optional[int],
        tier_survival_cache: Optional[Dict[Tuple[str, int], Optional[float]]] = None,
    ) -> Dict[str, Any]:
        player_survival = survival_probability(player.get("adp"), next_pick)
        tier_key = (player["position"], tier_number(player.get("tier")))
        if tier_survival_cache is not None and tier_key in tier_survival_cache:
            tier_survival = tier_survival_cache[tier_key]
        else:
            tier_survival = self.tier_survival_probability(
                tier_key[0], tier_key[1], next_pick
            )
            if tier_survival_cache is not None:
                tier_survival_cache[tier_key] = tier_survival
        status = wait_status(player_survival)
        if next_pick is None:
            reason = "No later user pick remains, so waiting is not applicable."
        elif player_survival is None:
            reason = "ADP evidence is missing, so player survival cannot be estimated."
        else:
            reason = "Estimated {:.0%} player survival".format(player_survival)
            if tier_survival is not None:
                reason += " and {:.0%} chance that someone in the tier remains".format(
                    tier_survival
                )
            reason += "."
        return {
            "status": status,
            "player_survival": player_survival,
            "tier_survival": tier_survival,
            "reason": reason,
            "method": "adp_logistic_tier_independence_heuristic",
        }

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
        replacement_levels: Dict[str, Dict[str, Any]],
    ) -> Tuple[float, Dict[str, float], List[str]]:
        position = player["position"]
        overall_rank = int(player.get("overall_rank") or 999)
        position_rank = int(player.get("position_rank") or 999)
        projection = self._projection(player)
        replacement = replacement_levels[position]
        league_vorp = projection - float(replacement["baseline_points"])
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
            "vorp_value": league_vorp * weights["vorp"],
            "tier_value": max(0.0, 6.0 - tier) * 8.0 * weights["tier"],
            "roster_need": float(needs[position]["score_adjustment"]),
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
            "Tier {} with {:.1f} league-adjusted VORP".format(tier, league_vorp),
        ]
        if needs[position]["needed"]:
            reasons.append("fills an open {} starter slot".format(position))
        elif needs[position]["need_level"] == "flex":
            reasons.append("can fill an open FLEX slot")
        elif needs[position]["need_level"] in {"at_capacity", "excess"}:
            reasons.append("would exceed the current {} balance target".format(position))
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
        replacement_levels = self.replacement_levels()
        roster_warnings = self.roster_balance_warnings(needs)
        next_user_pick = next_pick_for_team(
            self.session.current_pick + 1,
            self.session.user_team,
            self.session.league_size,
            self.session.rounds,
        )
        candidates = self.session.available_players()
        scored = []
        tier_survival_cache: Dict[Tuple[str, int], Optional[float]] = {}
        for player in candidates:
            score, components, reasons = self._candidate_score(
                player, mode, needs, tiers, run, next_user_pick, replacement_levels
            )
            replacement = replacement_levels[player["position"]]
            league_vorp = self._projection(player) - float(replacement["baseline_points"])
            wait = self.wait_assessment(
                player, next_user_pick, tier_survival_cache=tier_survival_cache
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
                "vorp": round(league_vorp, 3),
                "source_vorp": player.get("vorp"),
                "replacement_rank": replacement["replacement_rank"],
                "replacement_points": replacement["baseline_points"],
                "adp": player.get("adp"),
                "bye_week": player.get("bye_week"),
                "survival_to_next_pick": wait["player_survival"],
                "tier_survival_to_next_pick": wait["tier_survival"],
                "can_wait": wait["status"],
                "can_wait_reason": wait["reason"],
                "recommendation_score": score,
                "score_components": {key: round(value, 3) for key, value in components.items()},
                "reasons": reasons,
                "caveats": self.candidate_caveats(player, needs),
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
                "roster_balance_warnings": roster_warnings,
                "replacement_levels": replacement_levels,
                "tiers": tiers,
                "position_run": run,
                "candidate_pool": {
                    "available": len(candidates),
                    "scored": len(scored),
                    "scope": "all_available_players",
                },
            },
        }

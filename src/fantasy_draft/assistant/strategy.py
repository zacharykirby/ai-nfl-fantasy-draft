"""Read-only strategic assessment for an upcoming user draft turn."""

import json
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Set

from fantasy_draft.assistant.service import compact_player
from fantasy_draft.draft.recommendations import (
    DEFAULT_STARTERS,
    DraftRecommendationEngine,
    MODES,
    survival_probability,
)
from fantasy_draft.draft.session import (
    BOARD_POSITIONS,
    DraftSession,
    next_pick_for_team,
    snake_team_for_pick,
)
from fantasy_draft.providers.openrouter import OpenRouterClient, parse_json_object


STRATEGY_SCHEMA_VERSION = "1.0"
STRATEGIES = {
    "take_best_value",
    "take_position_now",
    "take_primary_if_available",
    "wait_on_position",
    "avoid_position_reach",
    "balanced",
}
MAX_CAUTIONS = 3


class StrategyResponseError(ValueError):
    pass


def _team_roster_state(session: DraftSession, team: int) -> Dict[str, Any]:
    counts = Counter(player["position"] for player in session.roster(team))
    starters = dict(DEFAULT_STARTERS)
    starters.update(session.payload.get("league", {}).get("starters", {}))
    roster_counts = {position: int(counts.get(position, 0)) for position in BOARD_POSITIONS}
    needs = {
        position: {
            "rostered": roster_counts[position],
            "base_starters": int(starters.get(position, 0) or 0),
            "open_base_slots": max(
                0, int(starters.get(position, 0) or 0) - roster_counts[position]
            ),
            "needed": roster_counts[position] < int(starters.get(position, 0) or 0),
        }
        for position in BOARD_POSITIONS
    }
    return {"team": team, "counts": roster_counts, "needs": needs}


class DraftStrategyContextBuilder:
    """Build a bounded evidence packet focused on positional urgency."""

    def __init__(self, session: DraftSession):
        self.session = session

    def build(self, mode: str = "balanced", per_position: int = 4) -> Dict[str, Any]:
        if mode not in MODES:
            raise ValueError("mode must be safe, balanced, or upside")
        recommendation = DraftRecommendationEngine(self.session).recommend(
            mode=mode, alternatives=5
        )
        current_pick = self.session.current_pick
        user_pick = next_pick_for_team(
            current_pick, self.session.user_team, self.session.league_size, self.session.rounds
        )
        following_pick = next_pick_for_team(
            (user_pick + 1) if user_pick is not None else current_pick,
            self.session.user_team,
            self.session.league_size,
            self.session.rounds,
        )
        stop = following_pick or (self.session.league_size * self.session.rounds + 1)
        intervening_picks = [
            {"overall_pick": pick, "team": snake_team_for_pick(pick, self.session.league_size)}
            for pick in range((user_pick + 1) if user_pick is not None else current_pick, stop)
        ]
        intervening_teams = []
        seen = set()
        for item in intervening_picks:
            if item["team"] not in seen:
                seen.add(item["team"])
                intervening_teams.append(_team_roster_state(self.session, item["team"]))

        top_by_position: Dict[str, List[Dict[str, Any]]] = {}
        candidates: Dict[str, Dict[str, Any]] = {}
        for position in BOARD_POSITIONS:
            views = []
            for player in self.session.available_players(position)[:per_position]:
                view = compact_player(player)
                view["survival_to_following_pick"] = survival_probability(
                    player.get("adp"), following_pick
                )
                views.append(view)
                candidates[player["player_id"]] = view
            top_by_position[position] = views
        for item in [recommendation["primary"]] + recommendation["alternatives"]:
            player = self.session.player_index()[item["player_id"]]
            view = compact_player(player)
            view["survival_to_following_pick"] = survival_probability(
                player.get("adp"), following_pick
            )
            candidates[player["player_id"]] = view

        return {
            "schema_version": STRATEGY_SCHEMA_VERSION,
            "league": {
                "scoring": self.session.payload["league"].get("scoring"),
                "league_size": self.session.league_size,
                "rounds": self.session.rounds,
                "starters": self.session.payload["league"].get("starters", {}),
                "bench_size": self.session.payload["league"].get("bench_size"),
            },
            "draft": {
                "current_pick": current_pick,
                "current_team": self.session.current_team,
                "user_team": self.session.user_team,
                "user_pick": user_pick,
                "following_user_pick": following_pick,
                "picks_until_user": None if user_pick is None else user_pick - current_pick,
            },
            "user_roster": [compact_player(player) for player in self.session.roster()],
            "user_needs": recommendation["signals"]["roster_needs"],
            "team_roster_construction": [
                _team_roster_state(self.session, team)
                for team in range(1, self.session.league_size + 1)
            ],
            "intervening_before_following_pick": {
                "picks": intervening_picks,
                "teams": intervening_teams,
            },
            "recent_selections": [
                {key: event[key] for key in ("overall_pick", "team", "player", "position")}
                for event in self.session.active_selections()[-10:]
            ],
            "position_run": recommendation["signals"]["position_run"],
            "tier_state": recommendation["signals"]["tiers"],
            "top_available_by_position": top_by_position,
            "deterministic_recommendation": recommendation,
            "candidate_pool": list(candidates.values()),
            "constraints": {
                "candidate_names": sorted(player["player"] for player in candidates.values()),
                "supported_positions": list(BOARD_POSITIONS),
                "state_mutation_allowed": False,
            },
        }


def build_strategy_messages(context: Dict[str, Any]) -> List[Dict[str, str]]:
    system = """Assess the positional strategy for the user's upcoming fantasy draft pick.
Use only the supplied DRAFT_CONTEXT. Do not rely on outside memory for players, teams,
projections, rankings, injuries, availability, or draft state. Determine which positions
are urgent or can wait, whether recent runs are actionable, which intervening teams may
take relevant positions, whether to follow the deterministic recommendation, and which
allowlisted candidates execute the strategy. Do not mutate draft state. Return only a
JSON object with exactly: summary, strategy, primary_player, fallback_players,
position_priority, wait_positions, cautions, confidence. Keep it concise for a phone
screen and do not provide chain-of-thought."""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "DRAFT_CONTEXT:\n" + json.dumps(context, separators=(",", ":"))},
    ]


def validate_strategy_response(payload: Dict[str, Any], allowed_names: Set[str]) -> Dict[str, Any]:
    required = {
        "summary", "strategy", "primary_player", "fallback_players",
        "position_priority", "wait_positions", "cautions", "confidence",
    }
    if set(payload) != required:
        raise StrategyResponseError("Model response fields do not match the strategy schema")
    if not isinstance(payload["summary"], str) or not payload["summary"].strip():
        raise StrategyResponseError("summary must be nonempty text")
    if payload["strategy"] not in STRATEGIES:
        raise StrategyResponseError("invalid strategy")
    primary = payload["primary_player"]
    if primary is not None and (not isinstance(primary, str) or primary not in allowed_names):
        raise StrategyResponseError("primary_player is unavailable or outside the allowlist")
    fallbacks = payload["fallback_players"]
    if not isinstance(fallbacks, list) or len(fallbacks) > 3:
        raise StrategyResponseError("fallback_players must contain at most three players")
    if any(not isinstance(name, str) or name not in allowed_names for name in fallbacks):
        raise StrategyResponseError("fallback player is unavailable or outside the allowlist")
    named = ([primary] if primary is not None else []) + fallbacks
    if len(named) != len(set(named)):
        raise StrategyResponseError("primary and fallback players must be unique")
    for field in ("position_priority", "wait_positions"):
        values = payload[field]
        if not isinstance(values, list) or len(values) > len(BOARD_POSITIONS):
            raise StrategyResponseError("{} must be a bounded position array".format(field))
        if len(values) != len(set(values)) or any(value not in BOARD_POSITIONS for value in values):
            raise StrategyResponseError("{} contains invalid or duplicate positions".format(field))
    cautions = payload["cautions"]
    if not isinstance(cautions, list) or len(cautions) > MAX_CAUTIONS or not all(
        isinstance(item, str) and item.strip() for item in cautions
    ):
        raise StrategyResponseError("cautions must be a bounded array of nonempty strings")
    if isinstance(payload["confidence"], bool):
        raise StrategyResponseError("confidence must be numeric")
    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        raise StrategyResponseError("confidence must be numeric")
    if not 0 <= confidence <= 1:
        raise StrategyResponseError("confidence must be between 0 and 1")
    cleaned = dict(payload)
    cleaned["summary"] = payload["summary"].strip()
    cleaned["confidence"] = round(confidence, 3)
    return cleaned


def local_strategy(context: Dict[str, Any], error: str) -> Dict[str, Any]:
    recommendation = context["deterministic_recommendation"]
    primary = recommendation["primary"]
    urgent = [
        position for position, state in context["tier_state"].items()
        if state.get("tier_drop_imminent")
    ]
    priority = [primary["position"]] + [position for position in urgent if position != primary["position"]]
    priority += [position for position in BOARD_POSITIONS if position not in priority]
    wait = [
        position for position in BOARD_POSITIONS
        if not context["user_needs"][position]["needed"] and position != primary["position"]
    ]
    summary = "{} is the deterministic value.".format(primary["player"])
    if urgent:
        summary += " {} has an imminent tier drop.".format("/".join(urgent))
    return {
        "summary": summary,
        "strategy": "take_primary_if_available",
        "primary_player": primary["player"],
        "fallback_players": [item["player"] for item in recommendation["alternatives"][:2]],
        "position_priority": priority[:4],
        "wait_positions": wait[:3],
        "cautions": ["Model strategy unavailable; this plan uses local draft signals."],
        "confidence": recommendation["confidence"],
        "error": error,
    }


class DraftStrategyService:
    """Run one assessment, then re-read local state to establish freshness."""

    def __init__(self, session_path: Path, client: Optional[OpenRouterClient] = None, timeout: int = 5):
        self.session_path = Path(session_path)
        self.client = client or OpenRouterClient()
        self.timeout = max(3, min(int(timeout), 6))

    def assess(self, mode: str = "balanced", generated_for_pick: Optional[int] = None) -> Dict[str, Any]:
        session = DraftSession.load(self.session_path)
        if session.current_team is None or session.payload["session"]["status"] != "active":
            raise ValueError("Draft is not active")
        if next_pick_for_team(session.current_pick, session.user_team, session.league_size, session.rounds) is None:
            raise ValueError("The user has no upcoming pick")
        if generated_for_pick is not None and generated_for_pick != session.current_pick:
            raise ValueError("generated_for_pick does not match the current pick")
        generated_pick = session.current_pick
        generated_revision = session.payload["session"]["updated_at"]
        context = DraftStrategyContextBuilder(session).build(mode=mode)
        allowed = set(context["constraints"]["candidate_names"])
        started = perf_counter()
        source = "model"
        try:
            response = self.client.chat(
                messages=build_strategy_messages(context), temperature=0.1, max_tokens=500,
                response_format={"type": "json_object"}, timeout=self.timeout,
            )
            if response.startswith("Error:"):
                raise StrategyResponseError(response)
            assessment = validate_strategy_response(parse_json_object(response), allowed)
        except Exception as exc:
            source = "deterministic_fallback"
            assessment = local_strategy(context, str(exc))
        latency_ms = round((perf_counter() - started) * 1000)

        latest = DraftSession.load(self.session_path)
        current_revision = latest.payload["session"]["updated_at"]
        available = {player["player"] for player in latest.available_players()}
        named = ([assessment["primary_player"]] if assessment["primary_player"] else []) + assessment["fallback_players"]
        primary_available = assessment["primary_player"] is None or assessment["primary_player"] in available
        players_available = all(name in available for name in named)
        stale = generated_revision != current_revision or generated_pick != latest.current_pick or not players_available
        return {
            "assessment": assessment,
            "freshness": {
                "generated_for_pick": generated_pick,
                "current_pick": latest.current_pick,
                "generated_revision": generated_revision,
                "current_revision": current_revision,
                "stale": stale,
                "primary_available": primary_available,
                "players_available": players_available,
            },
            "source": source,
            "model": getattr(self.client, "model", None),
            "latency_ms": latency_ms,
        }

"""User-triggered, read-only situational draft co-pilot."""

import json
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Set

from fantasy_draft.draft.recommendations import (
    DEFAULT_STARTERS,
    DraftRecommendationEngine,
    survival_probability,
    tier_number,
)
from fantasy_draft.draft.session import (
    BOARD_POSITIONS,
    DraftSession,
    next_pick_for_team,
    snake_team_for_pick,
)
from fantasy_draft.providers.openrouter import OpenRouterClient, parse_json_object


COPILOT_SCHEMA_VERSION = "oh_god.v1"
CONTEXT_SCHEMA_VERSION = "oh_god_context.v1"
CLOSE_SCORE_THRESHOLD = 5.0
FOLLOW_UP_INTENTS = {"can_i_wait", "why_not_safe", "more_upside"}
URGENCIES = {"low", "medium", "high"}
SITUATION_TYPES = {
    "value_fall",
    "tier_cliff",
    "position_run",
    "roster_pressure",
    "normal_board",
    "data_uncertain",
    "mixed",
}
WAIT_VALUES = {"yes", "probably", "risky", "no", "unknown"}
FORECAST_FRESHNESS = {"fresh", "warning", "stale", "unknown"}
OPTION_FIELDS = {"player_id", "label", "reason"}
RESULT_FIELDS = {
    "schema_version",
    "headline",
    "urgency",
    "situation_type",
    "explanation",
    "primary_option",
    "safe_option",
    "upside_option",
    "can_wait",
    "can_wait_reason",
    "caveats",
    "evidence_summary",
    "draft_revision",
}
EVIDENCE_FIELDS = {
    "candidate_score_gap",
    "close_call",
    "tier_cliffs",
    "recent_run_positions",
    "data_warning_count",
    "forecast_freshness",
}


class CopilotResponseError(ValueError):
    pass


def _bounded_text(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise CopilotResponseError("{} must be text".format(field))
    cleaned = " ".join(value.split())
    if not minimum <= len(cleaned) <= maximum:
        raise CopilotResponseError(
            "{} must contain {}-{} characters".format(field, minimum, maximum)
        )
    return cleaned


def _compact_roster_player(player: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "player_id": player.get("player_id"),
        "player": player.get("player"),
        "position": player.get("position"),
        "team": player.get("team"),
        "tier": player.get("tier"),
        "bye_week": player.get("bye_week"),
    }


def _team_state(session: DraftSession, team: int) -> Dict[str, Any]:
    counts = Counter(player["position"] for player in session.roster(team))
    starters = dict(DEFAULT_STARTERS)
    starters.update(session.payload.get("league", {}).get("starters", {}))
    position_counts = {
        position: int(counts.get(position, 0)) for position in BOARD_POSITIONS
    }
    likely_needs = [
        position
        for position in BOARD_POSITIONS
        if position_counts[position] < int(starters.get(position, 0) or 0)
    ]
    return {
        "team": team,
        "position_counts": position_counts,
        "likely_needs": likely_needs,
    }


def _first_distinct(
    recommendation: Dict[str, Any], used: Set[str]
) -> Optional[Dict[str, Any]]:
    for item in [recommendation["primary"]] + recommendation["alternatives"]:
        if item["player_id"] not in used:
            used.add(item["player_id"])
            return item
    return None


def _option(
    item: Optional[Dict[str, Any]], label: str
) -> Optional[Dict[str, Any]]:
    if item is None:
        return None
    reasons = item.get("reasons") or []
    reason = reasons[0] if reasons else "Strong deterministic candidate in this snapshot."
    return {
        "player_id": item["player_id"],
        "label": label,
        "reason": reason[:140],
    }


class OhGodContextBuilder:
    """Build the bounded `oh_god_context.v1` evidence packet."""

    def __init__(
        self,
        session: DraftSession,
        board_health: Optional[Dict[str, Any]] = None,
        board_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.session = session
        self.board_health = board_health or {}
        self.board_metadata = board_metadata or {}

    def build(self) -> Dict[str, Any]:
        engine = DraftRecommendationEngine(self.session)
        recommendations = {
            mode: engine.recommend(mode=mode, alternatives=8)
            for mode in ("balanced", "safe", "upside")
        }
        balanced = recommendations["balanced"]
        current_pick = self.session.current_pick
        user_pick = next_pick_for_team(
            current_pick,
            self.session.user_team,
            self.session.league_size,
            self.session.rounds,
        )
        following_pick = next_pick_for_team(
            (user_pick + 1) if user_pick is not None else current_pick,
            self.session.user_team,
            self.session.league_size,
            self.session.rounds,
        )
        tiers = balanced["signals"]["tiers"]
        run = balanced["signals"]["position_run"]
        needs = balanced["signals"]["roster_needs"]

        scored: Dict[str, Dict[str, Any]] = {}
        for recommendation in recommendations.values():
            for item in [recommendation["primary"]] + recommendation["alternatives"]:
                scored.setdefault(item["player_id"], item)
        for position in BOARD_POSITIONS:
            for player in self.session.available_players(position)[:3]:
                scored.setdefault(player["player_id"], {
                    "player_id": player["player_id"],
                    "player": player["player"],
                    "position": player["position"],
                    "team": player.get("team"),
                    "tier": player.get("tier"),
                    "projected_points": player.get("projected_points"),
                    "vorp": player.get("vorp"),
                    "adp": player.get("adp"),
                    "bye_week": player.get("bye_week"),
                    "recommendation_score": None,
                    "reasons": [],
                })
        used: Set[str] = set()
        primary = _first_distinct(recommendations["balanced"], used)
        safe = _first_distinct(recommendations["safe"], used)
        upside = _first_distinct(recommendations["upside"], used)
        option_items = [item for item in (primary, safe, upside) if item]
        option_ids = {item["player_id"] for item in option_items}
        ordered_items = option_items + [
            item for item in scored.values() if item["player_id"] not in option_ids
        ]
        player_index = self.session.player_index()
        leader_score = float(balanced["primary"]["recommendation_score"])
        candidates = []
        for item in ordered_items[:18]:
            player = player_index[item["player_id"]]
            score = item.get("recommendation_score")
            risk = player.get("risk", {})
            projection_method = player.get("projection_method")
            candidates.append({
                "player_id": item["player_id"],
                "player": item["player"],
                "position": item["position"],
                "team": item.get("team"),
                "model_score": score,
                "score_gap_from_leader": None
                if score is None else round(leader_score - float(score), 3),
                "close_to_leader": score is not None
                and leader_score - float(score) <= CLOSE_SCORE_THRESHOLD,
                "forecast_points": item.get("projected_points"),
                "forecast_uncertainty": "estimated"
                if projection_method == "adp_estimate" else "known",
                "vorp": item.get("vorp"),
                "source_vorp": item.get("source_vorp"),
                "replacement_rank": item.get("replacement_rank"),
                "replacement_points": item.get("replacement_points"),
                "tier": item.get("tier"),
                "players_left_in_tier": tiers[item["position"]]["remaining_in_best_tier"],
                "adp": item.get("adp"),
                "adp_delta_at_current_pick": None
                if item.get("adp") is None
                else round(current_pick - float(item["adp"]), 1),
                "survival_to_next_pick": survival_probability(
                    item.get("adp"), following_pick
                ),
                "tier_survival_to_next_pick": engine.tier_survival_probability(
                    item["position"], tier_number(item.get("tier")), following_pick
                ),
                "bye_week": item.get("bye_week"),
                "risk": risk,
                "flags": list(player.get("flags", []))[:6],
                "news": {
                    "freshness": "unknown",
                    "injury_flag": bool(risk.get("injury_flag")),
                },
                "reasons": list(item.get("reasons") or [])[:4],
                "caveats": list(item.get("caveats") or [])[:3],
            })
        score_gap = None
        if balanced["alternatives"]:
            score_gap = round(
                leader_score
                - float(balanced["alternatives"][0]["recommendation_score"]),
                3,
            )
        close_call = score_gap is not None and score_gap <= CLOSE_SCORE_THRESHOLD
        tier_cliffs = sorted(
            position for position, state in tiers.items()
            if state.get("tier_drop_imminent")
        )
        warning_issues = [
            issue for issue in self.board_health.get("issues", [])
            if issue.get("severity") in {"warning", "error"}
        ][:8]
        warning_codes = [str(issue.get("code")) for issue in warning_issues[:3]]
        freshness_status = self.board_health.get("freshness", {}).get("status", "unknown")
        forecast_freshness = {
            "ready": "fresh",
            "warning": "warning",
            "not_ready": "stale",
        }.get(freshness_status, "unknown")
        urgency = "high" if current_pick == user_pick else (
            "medium" if (user_pick is not None and user_pick - current_pick <= 4) else "low"
        )
        if tier_cliffs and urgency == "low":
            urgency = "medium"
        if warning_codes and self.board_health.get("status") != "ready":
            situation_type = "data_uncertain"
        elif tier_cliffs and run.get("positions"):
            situation_type = "mixed"
        elif tier_cliffs:
            situation_type = "tier_cliff"
        elif run.get("positions"):
            situation_type = "position_run"
        elif any(value.get("needed") for value in needs.values()):
            situation_type = "roster_pressure"
        else:
            situation_type = "normal_board"
        primary_wait = engine.wait_assessment(primary, following_pick) if primary else {
            "status": "unknown",
            "reason": "No available candidate can be assessed.",
        }
        can_wait = primary_wait["status"]

        recent_events = self.session.active_selections()[-8:]
        fallers = []
        reaches = []
        for event in recent_events:
            player = player_index.get(event["player_id"], {})
            adp = player.get("adp")
            if adp is None:
                continue
            delta = float(event["overall_pick"]) - float(adp)
            summary = {
                "player_id": event["player_id"],
                "player": event["player"],
                "delta": round(delta, 1),
            }
            if delta >= 8:
                fallers.append(summary)
            elif delta <= -8:
                reaches.append(summary)

        before_picks = []
        if user_pick is not None:
            before_picks = [
                {"overall_pick": pick, "team": snake_team_for_pick(pick, self.session.league_size)}
                for pick in range(current_pick, user_pick)
            ]
        before_teams = []
        seen_teams = set()
        for pick in before_picks:
            if pick["team"] not in seen_teams:
                seen_teams.add(pick["team"])
                before_teams.append(_team_state(self.session, pick["team"]))

        roster_counts = Counter(player["position"] for player in self.session.roster())
        return {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "draft": {
                "revision": self.session.payload["session"]["updated_at"],
                "current_pick": current_pick,
                "current_team": self.session.current_team,
                "user_team": self.session.user_team,
                "is_user_pick": self.session.current_team == self.session.user_team,
                "next_user_pick": user_pick,
                "following_user_pick": following_pick,
                "picks_until_user": None if user_pick is None else user_pick - current_pick,
                "round": ((current_pick - 1) // self.session.league_size) + 1,
            },
            "league": {
                "scoring": self.session.payload["league"].get("scoring"),
                "league_size": self.session.league_size,
                "rounds": self.session.rounds,
                "starters": self.session.payload["league"].get("starters", {}),
                "bench_size": self.session.payload["league"].get("bench_size"),
            },
            "board_health": {
                "snapshot_status": self.board_health.get("snapshot", {}).get("status", "ready"),
                "source_status": self.board_health.get("source", {}).get("status", "unknown"),
                "freshness_status": freshness_status,
                "generated_at": self.board_metadata.get("generated_at")
                or self.session.payload["board"].get("generated_at"),
                "retrieved_at": self.board_health.get("freshness", {}).get("metrics", {}).get("retrieved_at"),
                "news_source": self.board_metadata.get("news_source", "unknown"),
                "warning_codes": warning_codes,
                "warning_count": len(warning_issues),
            },
            "user_roster": {
                "players": [_compact_roster_player(player) for player in self.session.roster()],
                "position_counts": {
                    position: int(roster_counts.get(position, 0))
                    for position in BOARD_POSITIONS
                },
                "open_starter_slots": {
                    position: needs[position]["open_base_slots"]
                    for position in BOARD_POSITIONS
                },
                "warnings": balanced["signals"]["roster_balance_warnings"],
            },
            "recent_draft": {
                "selections": [
                    {
                        key: event[key]
                        for key in ("overall_pick", "team", "player_id", "player", "position")
                    }
                    for event in recent_events
                ],
                "position_run": run,
                "adp_behavior": {"fallers": fallers[:4], "reaches": reaches[:4]},
            },
            "before_next_user_pick": {
                "picks": before_picks[:16],
                "teams": before_teams[:12],
            },
            "position_state": {
                position: {
                    "available": len(self.session.available_players(position)),
                    "best_tier": tiers[position]["best_tier"],
                    "remaining_in_tier": tiers[position]["remaining_in_best_tier"],
                    "next_tier": tiers[position]["next_tier"],
                }
                for position in BOARD_POSITIONS
            },
            "candidates": candidates,
            "deterministic_assessment": {
                "primary_player_id": primary["player_id"] if primary else None,
                "safe_player_id": safe["player_id"] if safe else None,
                "upside_player_id": upside["player_id"] if upside else None,
                "urgency": urgency,
                "situation_type": situation_type,
                "can_wait": can_wait,
                "can_wait_reason": primary_wait["reason"],
                "close_score_threshold": CLOSE_SCORE_THRESHOLD,
                "leader_gap": score_gap,
            },
            "constraints": {
                "available_player_ids": sorted(item["player_id"] for item in candidates),
                "state_mutation_allowed": False,
                "max_options": 3,
                "max_caveats": 3,
                "must_disclose_warning_codes": warning_codes,
            },
            "_local_options": {
                "primary_option": _option(primary, "Model/data lean"),
                "safe_option": _option(safe, "Safer build"),
                "upside_option": _option(upside, "Upside swing"),
            },
            "_evidence_summary": {
                "candidate_score_gap": score_gap,
                "close_call": close_call,
                "tier_cliffs": tier_cliffs,
                "recent_run_positions": list(run.get("positions", [])),
                "data_warning_count": len(warning_issues),
                "forecast_freshness": forecast_freshness,
            },
        }


def model_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Remove server-only fallback helpers before sending bounded context."""
    return {key: value for key, value in context.items() if not key.startswith("_")}


def build_copilot_messages(context: Dict[str, Any]) -> List[Dict[str, str]]:
    system = """Explain the current fantasy draft situation using only OH_GOD_CONTEXT.
Do not use outside player, injury, news, ranking, or availability knowledge. Return one
JSON object matching oh_god.v1 exactly. Use only allowlisted player_id values. Keep the
headline memorable but make uncertainty and close scores explicit. Do not mutate state,
claim certainty, or provide hidden reasoning. Options must be distinct and may be null."""
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "OH_GOD_CONTEXT:\n" + json.dumps(
                model_context(context), separators=(",", ":")
            ),
        },
    ]


def _validate_option(
    option: Any,
    field: str,
    allowed_ids: Set[str],
    expected_label: str,
) -> Optional[Dict[str, Any]]:
    if option is None:
        return None
    if not isinstance(option, dict) or set(option) != OPTION_FIELDS:
        raise CopilotResponseError("{} does not match the option schema".format(field))
    if option["player_id"] not in allowed_ids:
        raise CopilotResponseError("{} references an unavailable player".format(field))
    if option["label"] != expected_label:
        raise CopilotResponseError("{} has the wrong label".format(field))
    return {
        "player_id": option["player_id"],
        "label": option["label"],
        "reason": _bounded_text(option["reason"], field + ".reason", 1, 140),
    }


def validate_copilot_response(
    payload: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != RESULT_FIELDS:
        raise CopilotResponseError("Model response fields do not match oh_god.v1")
    if payload["schema_version"] != COPILOT_SCHEMA_VERSION:
        raise CopilotResponseError("Unsupported OH GOD schema version")
    if payload["draft_revision"] != context["draft"]["revision"]:
        raise CopilotResponseError("Model returned the wrong draft revision")
    if payload["urgency"] not in URGENCIES:
        raise CopilotResponseError("Invalid urgency")
    if payload["situation_type"] not in SITUATION_TYPES:
        raise CopilotResponseError("Invalid situation type")
    if payload["can_wait"] not in WAIT_VALUES:
        raise CopilotResponseError("Invalid can_wait value")
    assessment = context["deterministic_assessment"]
    if payload["can_wait"] != assessment["can_wait"]:
        raise CopilotResponseError("Model changed the deterministic wait assessment")
    _bounded_text(payload["can_wait_reason"], "can_wait_reason", 1, 180)
    allowed = set(context["constraints"]["available_player_ids"])
    options = {
        "primary_option": _validate_option(
            payload["primary_option"], "primary_option", allowed, "Model/data lean"
        ),
        "safe_option": _validate_option(
            payload["safe_option"], "safe_option", allowed, "Safer build"
        ),
        "upside_option": _validate_option(
            payload["upside_option"], "upside_option", allowed, "Upside swing"
        ),
    }
    ids = [option["player_id"] for option in options.values() if option]
    if len(ids) != len(set(ids)):
        raise CopilotResponseError("OH GOD options must be distinct")
    expected_primary = assessment["primary_player_id"]
    if expected_primary and (
        options["primary_option"] is None
        or options["primary_option"]["player_id"] != expected_primary
    ):
        raise CopilotResponseError("Model changed the deterministic primary lean")
    caveats = payload["caveats"]
    if not isinstance(caveats, list) or len(caveats) > 3:
        raise CopilotResponseError("caveats must contain at most three strings")
    cleaned_caveats = [
        _bounded_text(item, "caveat", 1, 140) for item in caveats
    ]
    evidence = payload["evidence_summary"]
    if not isinstance(evidence, dict) or set(evidence) != EVIDENCE_FIELDS:
        raise CopilotResponseError("evidence_summary does not match the schema")
    canonical_evidence = context["_evidence_summary"]
    if evidence != canonical_evidence:
        raise CopilotResponseError("Model evidence summary changed deterministic facts")
    required_warnings = context["constraints"]["must_disclose_warning_codes"]
    warning_caveats = ["Data warning: {}.".format(code) for code in required_warnings]
    primary = options["primary_option"]
    primary_candidate = next(
        (
            item for item in context["candidates"]
            if primary and item["player_id"] == primary["player_id"]
        ),
        {},
    )
    grounded_caveats = warning_caveats + list(primary_candidate.get("caveats", []))
    grounded_caveats.extend(
        warning["message"] for warning in context["user_roster"]["warnings"]
    )
    cleaned_caveats = (
        grounded_caveats
        + [item for item in cleaned_caveats if item not in grounded_caveats]
    )[:3]
    return {
        "schema_version": COPILOT_SCHEMA_VERSION,
        "headline": _bounded_text(payload["headline"], "headline", 1, 80),
        "urgency": payload["urgency"],
        "situation_type": payload["situation_type"],
        "explanation": _bounded_text(payload["explanation"], "explanation", 1, 320),
        **options,
        "can_wait": payload["can_wait"],
        "can_wait_reason": assessment["can_wait_reason"],
        "caveats": cleaned_caveats,
        "evidence_summary": canonical_evidence,
        "draft_revision": payload["draft_revision"],
    }


def local_copilot(context: Dict[str, Any], _error: str) -> Dict[str, Any]:
    assessment = context["deterministic_assessment"]
    evidence = context["_evidence_summary"]
    options = context["_local_options"]
    run = evidence["recent_run_positions"]
    cliffs = evidence["tier_cliffs"]
    if evidence["close_call"]:
        headline = "THIS ONE IS CLOSE. YOU ARE NOT MISSING A SECRET."
    elif run:
        headline = "THE ROOM IS RUNNING. YOU DO NOT HAVE TO SPRINT."
    elif cliffs:
        headline = "ONE TIER IS GETTING THIN. THAT IS THE REAL PRESSURE."
    else:
        headline = "THE BOARD IS WEIRD. YOU ARE STILL FINE."
    primary = options["primary_option"]
    primary_name = next(
        (
            item["player"] for item in context["candidates"]
            if primary and item["player_id"] == primary["player_id"]
        ),
        "the top local candidate",
    )
    explanation = "{} is the current data lean".format(primary_name)
    if evidence["close_call"]:
        explanation += ", but the leading candidates are effectively close"
    if cliffs:
        explanation += ". The clearest tier pressure is at {}".format("/".join(cliffs))
    elif run:
        explanation += ". The recent {} run is visible, not automatically actionable".format(
            "/".join(run)
        )
    explanation += "."
    can_wait = assessment["can_wait"]
    wait_reason = assessment["can_wait_reason"]
    evidence_caveats = [
        "Data warning: {}.".format(code)
        for code in context["constraints"]["must_disclose_warning_codes"]
    ]
    primary_candidate = next(
        (
            item for item in context["candidates"]
            if primary and item["player_id"] == primary["player_id"]
        ),
        {},
    )
    evidence_caveats.extend(primary_candidate.get("caveats", []))
    evidence_caveats.extend(
        warning["message"] for warning in context["user_roster"]["warnings"]
    )
    caveats = evidence_caveats[:2]
    caveats.append("Model interpretation unavailable; this card uses deterministic draft signals.")
    return {
        "schema_version": COPILOT_SCHEMA_VERSION,
        "headline": headline[:80],
        "urgency": assessment["urgency"],
        "situation_type": assessment["situation_type"],
        "explanation": explanation[:320],
        **options,
        "can_wait": can_wait,
        "can_wait_reason": wait_reason,
        "caveats": caveats[:3],
        "evidence_summary": evidence,
        "draft_revision": context["draft"]["revision"],
    }


class OhGodService:
    """Run an explicit analysis, then re-read state to establish freshness."""

    def __init__(
        self,
        session_path: Path,
        client: Optional[OpenRouterClient] = None,
        timeout: int = 5,
        board_health: Optional[Dict[str, Any]] = None,
        board_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.session_path = Path(session_path)
        self.client = client or OpenRouterClient()
        self.timeout = max(3, min(int(timeout), 6))
        self.board_health = board_health or {}
        self.board_metadata = board_metadata or {}

    def _context(self, session: DraftSession) -> Dict[str, Any]:
        return OhGodContextBuilder(
            session,
            board_health=self.board_health,
            board_metadata=self.board_metadata,
        ).build()

    def assess(self, generated_for_pick: int, draft_revision: str) -> Dict[str, Any]:
        session = DraftSession.load(self.session_path)
        if session.payload["session"]["status"] != "active":
            raise ValueError("Draft is not active")
        if generated_for_pick != session.current_pick:
            raise ValueError("generated_for_pick does not match the current pick")
        if draft_revision != session.payload["session"]["updated_at"]:
            raise ValueError("draft_revision does not match the current draft")
        context = self._context(session)
        started = perf_counter()
        source = "model"
        try:
            response = self.client.chat(
                messages=build_copilot_messages(context),
                temperature=0.2,
                max_tokens=700,
                response_format={"type": "json_object"},
                timeout=self.timeout,
            )
            if response.startswith("Error:"):
                raise CopilotResponseError(response)
            result = validate_copilot_response(parse_json_object(response), context)
        except Exception as exc:
            source = "deterministic_fallback"
            result = local_copilot(context, str(exc))
        latency_ms = round((perf_counter() - started) * 1000)

        latest = DraftSession.load(self.session_path)
        current_revision = latest.payload["session"]["updated_at"]
        available_ids = {player["player_id"] for player in latest.available_players()}
        option_ids = [
            option["player_id"]
            for option in (
                result.get("primary_option"),
                result.get("safe_option"),
                result.get("upside_option"),
            )
            if option
        ]
        options_available = all(player_id in available_ids for player_id in option_ids)
        stale = (
            draft_revision != current_revision
            or generated_for_pick != latest.current_pick
            or not options_available
        )
        return {
            "result": result,
            "source": source,
            "model": getattr(self.client, "model", None),
            "freshness": {
                "stale": stale,
                "generated_for_pick": generated_for_pick,
                "current_pick": latest.current_pick,
                "generated_revision": draft_revision,
                "current_revision": current_revision,
                "options_available": options_available,
            },
            "latency_ms": latency_ms,
            "timeout_seconds": self.timeout,
        }

    def follow_up(self, intent: str, draft_revision: str) -> Dict[str, Any]:
        if intent not in FOLLOW_UP_INTENTS:
            raise ValueError("Unsupported OH GOD follow-up intent")
        session = DraftSession.load(self.session_path)
        current_revision = session.payload["session"]["updated_at"]
        if current_revision != draft_revision:
            return {
                "intent": intent,
                "answer": "The draft changed. Tap OH GOD again for the current board.",
                "draft_revision": draft_revision,
                "freshness": {
                    "stale": True,
                    "generated_revision": draft_revision,
                    "current_revision": current_revision,
                },
                "source": "deterministic_fallback",
            }
        context = self._context(session)
        result = local_copilot(context, "contextual follow-up")
        if intent == "can_i_wait":
            answer = result["can_wait_reason"]
        elif intent == "why_not_safe":
            option = result.get("safe_option")
            answer = option["reason"] if option else "No distinct safer option is available in this snapshot."
        else:
            option = result.get("upside_option")
            answer = option["reason"] if option else "No distinct upside option is available in this snapshot."
        return {
            "intent": intent,
            "answer": answer[:240],
            "draft_revision": draft_revision,
            "freshness": {
                "stale": False,
                "generated_revision": draft_revision,
                "current_revision": current_revision,
            },
            "source": "deterministic_fallback",
        }

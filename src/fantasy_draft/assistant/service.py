#!/usr/bin/env python3
"""Controlled model reasoning over deterministic live-draft facts."""

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Set

from fantasy_draft.draft.recommendations import DraftRecommendationEngine, MODES
from fantasy_draft.draft.session import DraftSession
from fantasy_draft.providers.openrouter import OpenRouterClient, parse_json_object


ASSISTANT_SCHEMA_VERSION = "1.0"


class AssistantResponseError(ValueError):
    pass


def compact_player(player: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "player": player.get("player"),
        "position": player.get("position"),
        "team": player.get("team"),
        "position_rank": player.get("position_rank"),
        "overall_rank": player.get("overall_rank"),
        "tier": player.get("tier"),
        "projected_points": player.get("projected_points"),
        "vorp": player.get("vorp"),
        "adp": player.get("adp"),
        "projection_method": player.get("projection_method"),
        "risk": player.get("risk", {}),
        "flags": player.get("flags", []),
    }


class DraftAssistantContextBuilder:
    """Build bounded context; never send the entire board to the model."""

    def __init__(self, session: DraftSession):
        self.session = session

    def build(self, mode: str = "balanced", per_position: int = 3) -> Dict[str, Any]:
        recommendation = DraftRecommendationEngine(self.session).recommend(mode=mode, alternatives=5)
        candidates: Dict[str, Dict[str, Any]] = {}

        for item in [recommendation["primary"]] + recommendation["alternatives"]:
            player = self.session.player_index()[item["player_id"]]
            candidates[player["player_id"]] = compact_player(player)
        positional = {}
        for position in ("QB", "RB", "WR", "TE"):
            top = self.session.available_players(position)[:per_position]
            positional[position] = [compact_player(player) for player in top]
            for player in top:
                candidates[player["player_id"]] = compact_player(player)

        recent = self.session.active_selections()[-8:]
        roster = [compact_player(player) for player in self.session.roster()]
        return {
            "schema_version": "1.0",
            "league": {
                "scoring": self.session.payload["league"].get("scoring"),
                "league_size": self.session.league_size,
                "rounds": self.session.rounds,
                "starters": self.session.payload["league"].get("starters", {}),
                "user_team": self.session.user_team,
            },
            "draft": recommendation["generated_for"],
            "user_roster": roster,
            "recent_selections": [
                {
                    "overall_pick": event["overall_pick"],
                    "team": event["team"],
                    "player": event["player"],
                    "position": event["position"],
                }
                for event in recent
            ],
            "deterministic_recommendation": recommendation,
            "top_available_by_position": positional,
            "candidate_pool": list(candidates.values()),
            "constraints": {
                "candidate_names": sorted(player["player"] for player in candidates.values()),
                "state_mutation_allowed": False,
                "data_health": "ready",
            },
        }


def build_messages(question: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
    system = """You are the reasoning layer for a live fantasy football draft assistant.
Use only facts in DRAFT_CONTEXT. Do not use memory for player teams, projections, news,
rankings, availability, or draft state. You cannot change draft state. Recommend only
players listed in constraints.candidate_names. If the user asks to record a pick,
explain that they must use the explicit draft command.

Return only one JSON object with exactly these fields:
- schema_version: "1.0"
- answer: concise answer to the user's question
- recommendation: one candidate player name or null
- alternatives: array of zero to three candidate player names
- confidence: number from 0 to 1
- rationale: array of concise evidence-based reasons
- cautions: array of limitations or risks
- deterministic_agreement: boolean indicating whether recommendation matches the deterministic primary

Never include chain-of-thought or hidden reasoning. Rationale must be brief conclusions
grounded in supplied fields."""
    user = "QUESTION:\n{}\n\nDRAFT_CONTEXT:\n{}".format(
        question.strip(), json.dumps(context, separators=(",", ":"))
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def validate_model_response(
    payload: Dict[str, Any],
    allowed_names: Set[str],
    deterministic_primary: str,
) -> Dict[str, Any]:
    required = {
        "schema_version", "answer", "recommendation", "alternatives", "confidence",
        "rationale", "cautions", "deterministic_agreement",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise AssistantResponseError("Model response is missing: {}".format(", ".join(missing)))
    if payload["schema_version"] != ASSISTANT_SCHEMA_VERSION:
        raise AssistantResponseError("Model returned an unsupported schema version")
    if not isinstance(payload["answer"], str) or not payload["answer"].strip():
        raise AssistantResponseError("Model answer must be nonempty text")

    recommendation = payload["recommendation"]
    if recommendation is not None and recommendation not in allowed_names:
        raise AssistantResponseError("Model recommended unavailable player: {}".format(recommendation))
    alternatives = payload["alternatives"]
    if not isinstance(alternatives, list) or len(alternatives) > 3:
        raise AssistantResponseError("Model alternatives must be an array of at most three players")
    invalid = [name for name in alternatives if not isinstance(name, str) or name not in allowed_names]
    if invalid:
        raise AssistantResponseError("Model returned unavailable alternatives: {}".format(", ".join(map(str, invalid))))
    if recommendation in alternatives:
        raise AssistantResponseError("Model duplicated its primary recommendation in alternatives")
    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        raise AssistantResponseError("Model confidence must be numeric")
    if not 0 <= confidence <= 1:
        raise AssistantResponseError("Model confidence must be between 0 and 1")
    for field in ("rationale", "cautions"):
        if not isinstance(payload[field], list) or not all(isinstance(item, str) for item in payload[field]):
            raise AssistantResponseError("Model {} must be an array of strings".format(field))
    if not isinstance(payload["deterministic_agreement"], bool):
        raise AssistantResponseError("deterministic_agreement must be boolean")
    actual_agreement = recommendation == deterministic_primary if recommendation is not None else False
    if payload["deterministic_agreement"] != actual_agreement:
        raise AssistantResponseError("Model deterministic_agreement is inconsistent")

    cleaned = dict(payload)
    cleaned["answer"] = payload["answer"].strip()
    cleaned["confidence"] = round(confidence, 3)
    return cleaned


class LiveDraftAssistant:
    def __init__(self, session: DraftSession, client: Optional[OpenRouterClient] = None):
        self.session = session
        self.client = client or OpenRouterClient()

    def deterministic_fallback(
        self,
        question: str,
        context: Dict[str, Any],
        error: str,
    ) -> Dict[str, Any]:
        deterministic = context["deterministic_recommendation"]
        primary = deterministic["primary"]
        alternatives = deterministic["alternatives"][:3]
        return {
            "schema_version": ASSISTANT_SCHEMA_VERSION,
            "source": "deterministic_fallback",
            "model": getattr(self.client, "model", None),
            "question": question,
            "answer": "Take {} ({}). {}".format(
                primary["player"], primary["position"], primary["reasons"][0]
            ),
            "recommendation": primary["player"],
            "alternatives": [item["player"] for item in alternatives],
            "confidence": deterministic["confidence"],
            "rationale": primary["reasons"],
            "cautions": ["Model reasoning unavailable: {}".format(error)],
            "deterministic_agreement": True,
            "context_summary": self._context_summary(context),
        }

    @staticmethod
    def _context_summary(context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "current_pick": context["draft"]["current_pick"],
            "current_team": context["draft"]["current_team"],
            "next_user_pick": context["draft"]["next_user_pick"],
            "candidate_count": len(context["candidate_pool"]),
            "recent_selection_count": len(context["recent_selections"]),
        }

    def ask(self, question: str, mode: str = "balanced", timeout: int = 25) -> Dict[str, Any]:
        if not question or not question.strip():
            raise ValueError("question cannot be empty")
        if mode not in MODES:
            raise ValueError("mode must be safe, balanced, or upside")
        context = DraftAssistantContextBuilder(self.session).build(mode=mode)
        try:
            response = self.client.chat(
                messages=build_messages(question, context),
                temperature=0.1,
                max_tokens=700,
                response_format={"type": "json_object"},
                timeout=timeout,
            )
        except Exception as exc:
            return self.deterministic_fallback(
                question, context, "model request failed: {}".format(exc)
            )
        if response.startswith("Error:"):
            return self.deterministic_fallback(question, context, response)
        try:
            parsed = parse_json_object(response)
            validated = validate_model_response(
                parsed,
                set(context["constraints"]["candidate_names"]),
                context["deterministic_recommendation"]["primary"]["player"],
            )
        except Exception as exc:
            return self.deterministic_fallback(question, context, "invalid model response: {}".format(exc))

        validated.update({
            "source": "model",
            "model": self.client.model,
            "question": question,
            "context_summary": self._context_summary(context),
        })
        return validated


class DraftAssistantQueryService:
    """Run one read-only question and report whether draft state changed in flight."""

    def __init__(
        self,
        session_path: Path,
        client: Optional[OpenRouterClient] = None,
        timeout: int = 12,
    ):
        self.session_path = Path(session_path)
        self.client = client
        self.timeout = max(3, min(int(timeout), 25))

    def ask(self, question: str, mode: str = "balanced") -> Dict[str, Any]:
        session = DraftSession.load(self.session_path)
        generated_revision = session.payload["session"]["updated_at"]
        generated_for_pick = session.current_pick
        started = perf_counter()
        answer = LiveDraftAssistant(session, client=self.client).ask(
            question,
            mode=mode,
            timeout=self.timeout,
        )
        latency_ms = round((perf_counter() - started) * 1000)

        latest = DraftSession.load(self.session_path)
        current_revision = latest.payload["session"]["updated_at"]
        recommendation = answer.get("recommendation")
        available_names = {player["player"] for player in latest.available_players()}
        recommendation_available = recommendation is None or recommendation in available_names
        stale = generated_revision != current_revision or not recommendation_available
        return {
            "answer": answer,
            "freshness": {
                "stale": stale,
                "generated_for_pick": generated_for_pick,
                "current_pick": latest.current_pick,
                "recommendation_available": recommendation_available,
            },
            "latency_ms": latency_ms,
            "timeout_seconds": self.timeout,
        }

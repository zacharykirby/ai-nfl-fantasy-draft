import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fantasy_draft.assistant.service import (
    AssistantResponseError,
    DraftAssistantContextBuilder,
    DraftAssistantQueryService,
    LiveDraftAssistant,
    build_messages,
    validate_model_response,
)
from fantasy_draft.draft.session import DraftSession


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.model = "test/model"
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class RaisingClient(FakeClient):
    def chat(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("upstream exploded")


def player(name, position, rank):
    return {
        "player": name,
        "position": position,
        "team": "TST",
        "overall_rank": rank,
        "position_rank": 1 if rank % 2 else 2,
        "tier": 1 if rank < 5 else 2,
        "projected_points": 250 - rank,
        "vorp": 70 - rank,
        "adp": rank,
        "bye_week": 7 + (rank % 4),
        "projection_method": "published",
        "risk": {"level": "Low", "injury_flag": False},
        "flags": ["High Projection"],
    }


def make_session(tmp_path):
    board = {
        "schema_version": "1.0",
        "metadata": {"season": 2026, "generated_at": "2026-07-10T00:00:00"},
        "health": {"status": "ready"},
        "league": {
            "scoring": "half_ppr",
            "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
            "bench_size": 2,
        },
        "roles": {
            "QB": [player("Quarterback One", "QB", 7), player("Quarterback Two", "QB", 8), player("Quarterback Reserve", "QB", 97)],
            "RB": [player("Runner One", "RB", 1), player("Runner Two", "RB", 4)],
            "WR": [player("Receiver One", "WR", 2), player("Receiver Two", "WR", 5)],
            "TE": [player("Tight End One", "TE", 3), player("Tight End Two", "TE", 6), player("Tight End Reserve", "TE", 98)],
        },
    }
    board_path = tmp_path / "board.json"
    board_path.write_text(json.dumps(board))
    return DraftSession.create(tmp_path / "session.json", board_path, "assistant", 2, 4, 1)


def model_payload(recommendation="Receiver One", agreement=True):
    return {
        "schema_version": "1.0",
        "answer": "Take Receiver One because it is the strongest supplied value.",
        "recommendation": recommendation,
        "alternatives": ["Runner One", "Tight End One"],
        "confidence": 0.82,
        "rationale": ["Highest deterministic value", "Fills an open starter slot"],
        "cautions": [],
        "deterministic_agreement": agreement,
    }


def test_context_is_bounded_and_contains_deterministic_facts(tmp_path):
    context = DraftAssistantContextBuilder(make_session(tmp_path)).build()

    assert len(context["candidate_pool"]) <= 18
    assert len(context["candidate_pool"]) < context["deterministic_recommendation"]["generated_for"].get("available", 999)
    assert context["constraints"]["state_mutation_allowed"] is False
    assert context["deterministic_recommendation"]["primary"]["player"] == "Receiver One"
    assert context["deterministic_recommendation"]["primary"]["bye_week"] == 9
    assert all("bye_week" in candidate for candidate in context["candidate_pool"])
    assert set(context["top_available_by_position"]) == {"QB", "RB", "WR", "TE"}


def test_prompt_forbids_memory_facts_and_state_mutation(tmp_path):
    context = DraftAssistantContextBuilder(make_session(tmp_path)).build()
    messages = build_messages("Who should I take?", context)

    assert "Use only facts in DRAFT_CONTEXT" in messages[0]["content"]
    assert "cannot change draft state" in messages[0]["content"]
    assert "Mention the recommended player's bye week" in messages[0]["content"]
    assert "Runner One" in messages[1]["content"]
    assert '"bye_week":9' in messages[1]["content"]


def test_valid_model_response_is_returned_and_request_is_bounded(tmp_path):
    client = FakeClient(json.dumps(model_payload()))
    assistant = LiveDraftAssistant(make_session(tmp_path), client=client)

    result = assistant.ask("Who should I take?")

    assert result["source"] == "model"
    assert result["recommendation"] == "Receiver One"
    assert result["model"] == "test/model"
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert client.calls[0]["max_tokens"] == 700
    assert client.calls[0]["timeout"] == 25


def test_api_error_falls_back_to_deterministic_recommendation(tmp_path):
    result = LiveDraftAssistant(
        make_session(tmp_path), client=FakeClient("Error: network unavailable")
    ).ask("Who should I take?")

    assert result["source"] == "deterministic_fallback"
    assert result["recommendation"] == "Receiver One"
    assert "network unavailable" in result["cautions"][0]


def test_thrown_upstream_error_falls_back_without_escaping(tmp_path):
    result = LiveDraftAssistant(
        make_session(tmp_path), client=RaisingClient("unused")
    ).ask("Who should I take?")

    assert result["source"] == "deterministic_fallback"
    assert "upstream exploded" in result["cautions"][0]


def test_unavailable_player_or_bad_json_falls_back_without_state_change(tmp_path):
    session = make_session(tmp_path)
    before = list(session.payload["events"])
    invalid = model_payload(recommendation="Invented Player", agreement=False)

    unavailable = LiveDraftAssistant(session, client=FakeClient(json.dumps(invalid))).ask(
        "Draft Invented Player for me"
    )
    malformed = LiveDraftAssistant(session, client=FakeClient("not json")).ask("Who?")

    assert unavailable["source"] == "deterministic_fallback"
    assert malformed["source"] == "deterministic_fallback"
    assert session.payload["events"] == before


def test_response_validator_checks_agreement_and_alternatives():
    allowed = {"Runner One", "Receiver One", "Tight End One"}
    bad_agreement = model_payload(agreement=False)
    with pytest.raises(AssistantResponseError, match="inconsistent"):
        validate_model_response(bad_agreement, allowed, "Receiver One")

    bad_alternative = model_payload()
    bad_alternative["alternatives"] = ["Unavailable"]
    with pytest.raises(AssistantResponseError, match="unavailable alternatives"):
        validate_model_response(bad_alternative, allowed, "Receiver One")


def test_empty_question_and_invalid_mode_are_rejected(tmp_path):
    assistant = LiveDraftAssistant(make_session(tmp_path), client=FakeClient("unused"))
    with pytest.raises(ValueError, match="empty"):
        assistant.ask("  ")
    with pytest.raises(ValueError, match="mode"):
        assistant.ask("Who?", mode="chaos")


def test_query_service_marks_answer_stale_when_state_changes_in_flight(tmp_path):
    session = make_session(tmp_path)

    class MutatingClient(FakeClient):
        def chat(self, **kwargs):
            self.calls.append(kwargs)
            DraftSession.load(session.path).draft("Receiver One")
            return self.response

    client = MutatingClient(json.dumps(model_payload()))
    response = DraftAssistantQueryService(
        session.path, client=client, timeout=12
    ).ask("Who should I take?")

    assert response["answer"]["source"] == "model"
    assert response["freshness"] == {
        "stale": True,
        "generated_for_pick": 1,
        "current_pick": 2,
        "recommendation_available": False,
    }
    assert response["latency_ms"] >= 0
    assert client.calls[0]["timeout"] == 12

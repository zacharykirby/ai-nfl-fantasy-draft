import json

import pytest

from fantasy_draft.assistant.copilot import (
    COPILOT_SCHEMA_VERSION,
    CopilotResponseError,
    OhGodContextBuilder,
    OhGodService,
    local_copilot,
    model_context,
    validate_copilot_response,
)
from fantasy_draft.draft.session import DraftSession


def valid_copilot_response(context):
    options = context["_local_options"]
    return {
        "schema_version": COPILOT_SCHEMA_VERSION,
        "headline": "THE ROOM IS LOUD. THE BOARD IS STILL USEFUL.",
        "urgency": context["deterministic_assessment"]["urgency"],
        "situation_type": context["deterministic_assessment"]["situation_type"],
        "explanation": "The leading options are supported by the supplied deterministic evidence.",
        "primary_option": options["primary_option"],
        "safe_option": options["safe_option"],
        "upside_option": options["upside_option"],
        "can_wait": context["deterministic_assessment"]["can_wait"],
        "can_wait_reason": "Waiting depends on the supplied ADP survival estimate.",
        "caveats": [],
        "evidence_summary": context["_evidence_summary"],
        "draft_revision": context["draft"]["revision"],
    }


def test_oh_god_context_is_bounded_id_allowlisted_and_read_only(web_draft):
    context = OhGodContextBuilder(web_draft["session"]).build()
    public = model_context(context)

    assert public["schema_version"] == "oh_god_context.v1"
    assert public["draft"]["revision"] == web_draft["session"].payload["session"]["updated_at"]
    assert len(public["candidates"]) <= 18
    assert len(public["candidates"]) < len(web_draft["session"].payload["board"]["players"])
    assert set(public["constraints"]["available_player_ids"]) == {
        candidate["player_id"] for candidate in public["candidates"]
    }
    assert public["constraints"]["state_mutation_allowed"] is False
    assert all(key not in public for key in ("_local_options", "_evidence_summary"))


def test_copilot_validation_rejects_unknown_drafted_and_changed_evidence(web_draft):
    context = OhGodContextBuilder(web_draft["session"]).build()
    valid = valid_copilot_response(context)
    assert validate_copilot_response(valid, context)["schema_version"] == "oh_god.v1"

    unknown = valid_copilot_response(context)
    unknown["primary_option"] = {
        "player_id": "rb:not-on-board",
        "label": "Model/data lean",
        "reason": "Invented option.",
    }
    with pytest.raises(CopilotResponseError, match="unavailable"):
        validate_copilot_response(unknown, context)

    drafted_id = web_draft["session"].active_selections()[0]["player_id"]
    drafted = valid_copilot_response(context)
    drafted["primary_option"] = {
        "player_id": drafted_id,
        "label": "Model/data lean",
        "reason": "Already drafted.",
    }
    with pytest.raises(CopilotResponseError, match="unavailable"):
        validate_copilot_response(drafted, context)

    changed = valid_copilot_response(context)
    changed["evidence_summary"] = dict(changed["evidence_summary"])
    changed["evidence_summary"]["close_call"] = not changed["evidence_summary"]["close_call"]
    with pytest.raises(CopilotResponseError, match="deterministic facts"):
        validate_copilot_response(changed, context)


def test_oh_god_service_uses_explicit_revision_without_mutating(web_draft):
    context = OhGodContextBuilder(web_draft["session"]).build()

    class Client:
        model = "test/copilot"

        def chat(self, **kwargs):
            assert kwargs["timeout"] == 5
            assert "oh_god_context.v1" in kwargs["messages"][1]["content"]
            return json.dumps(valid_copilot_response(context))

    path = web_draft["session"].path
    before = path.read_bytes()
    result = OhGodService(path, Client()).assess(
        generated_for_pick=2,
        draft_revision=context["draft"]["revision"],
    )

    assert result["source"] == "model"
    assert result["freshness"]["stale"] is False
    assert result["result"]["draft_revision"] == context["draft"]["revision"]
    assert path.read_bytes() == before


def test_missing_model_and_timeout_return_useful_deterministic_fallback(web_draft):
    class OfflineClient:
        model = "offline/test"

        def chat(self, **_kwargs):
            raise TimeoutError("model timed out")

    session = web_draft["session"]
    result = OhGodService(session.path, OfflineClient()).assess(
        session.current_pick,
        session.payload["session"]["updated_at"],
    )

    assert result["source"] == "deterministic_fallback"
    assert result["result"]["primary_option"]["player_id"]
    assert "deterministic" in " ".join(result["result"]["caveats"]).lower()
    assert DraftSession.load(session.path).current_pick == 2


def test_response_becomes_stale_when_draft_advances(web_draft):
    path = web_draft["session"].path
    context = OhGodContextBuilder(web_draft["session"]).build()

    class AdvancingClient:
        model = "test/advancing"

        def chat(self, **_kwargs):
            latest = DraftSession.load(path)
            primary_id = context["_local_options"]["primary_option"]["player_id"]
            latest.draft(latest.player_index()[primary_id]["player"])
            return json.dumps(valid_copilot_response(context))

    result = OhGodService(path, AdvancingClient()).assess(
        2,
        context["draft"]["revision"],
    )

    assert result["freshness"]["stale"] is True
    assert result["freshness"]["options_available"] is False


def test_close_candidates_are_described_as_close(web_draft):
    context = OhGodContextBuilder(web_draft["session"]).build()
    context["_evidence_summary"]["close_call"] = True
    result = local_copilot(context, "offline")

    assert "CLOSE" in result["headline"]
    assert "effectively close" in result["explanation"]


def test_follow_up_is_enumerated_and_stale_safe(web_draft):
    session = web_draft["session"]
    service = OhGodService(session.path)
    revision = session.payload["session"]["updated_at"]

    current = service.follow_up("can_i_wait", revision)
    assert current["freshness"]["stale"] is False
    assert current["answer"]

    DraftSession.load(session.path).draft("Bijan Robinson")
    stale = service.follow_up("more_upside", revision)
    assert stale["freshness"]["stale"] is True

    with pytest.raises(ValueError, match="Unsupported"):
        service.follow_up("write_a_pick", revision)

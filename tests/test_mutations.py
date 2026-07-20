from concurrent.futures import ThreadPoolExecutor

import pytest

from fantasy_draft.draft.mutations import (
    DraftMutationService,
    DraftSessionCreationService,
    DraftSessionDeletionService,
    SessionAlreadyExistsError,
    StaleMutationError,
)
from fantasy_draft.draft.session import DraftSession, PlayerNotFoundError


def test_record_pick_is_idempotent_and_returns_fresh_cockpit(web_draft):
    path = web_draft["session"].path
    service = DraftMutationService(path)

    first = service.record_pick("Bijan", "request-pick-0001")
    replay = DraftMutationService(path).record_pick("Bijan", "request-pick-0001")

    assert first["replayed"] is False
    assert replay["replayed"] is True
    assert first["event"]["id"] == replay["event"]["id"]
    assert replay["cockpit"]["session"]["current_pick"] == 3
    assert len(DraftSession.load(path).active_selections()) == 2


def test_concurrent_retries_record_one_selection(web_draft):
    path = web_draft["session"].path

    def record():
        return DraftMutationService(path).record_pick("Bijan", "request-concurrent-1")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: record(), range(2)))

    assert sorted(result["replayed"] for result in results) == [False, True]
    assert len(DraftSession.load(path).active_selections()) == 2


def test_undo_is_idempotent(web_draft):
    path = web_draft["session"].path
    service = DraftMutationService(path)

    first = service.undo("request-undo-0001")
    replay = service.undo("request-undo-0001")

    assert first["replayed"] is False
    assert replay["replayed"] is True
    assert first["event"]["id"] == replay["event"]["id"]
    assert DraftSession.load(path).current_pick == 1


def test_bulk_pick_is_atomic_and_idempotent_across_service_restart(web_draft):
    path = web_draft["session"].path
    service = DraftMutationService(path)
    preview = service.preview_bulk(["Bijan", "Chase", "Bowers"])

    first = service.record_bulk(
        [event["player"] for event in preview["picks"]],
        "request-bulk-0001",
        preview["start_pick"],
    )
    replay = DraftMutationService(path).record_bulk(
        ["Bijan Robinson", "Ja'Marr Chase", "Brock Bowers"],
        "request-bulk-0001",
        preview["start_pick"],
    )

    assert [event["overall_pick"] for event in first["events"]] == [2, 3, 4]
    assert first["replayed"] is False
    assert replay["replayed"] is True
    assert [event["id"] for event in replay["events"]] == [
        event["id"] for event in first["events"]
    ]
    assert DraftSession.load(path).current_pick == 5


def test_failed_bulk_pick_leaves_file_and_session_unchanged(web_draft):
    path = web_draft["session"].path
    before = path.read_bytes()

    with pytest.raises(PlayerNotFoundError, match="No available player matched"):
        DraftMutationService(path).record_bulk(
            ["Bijan", "Definitely Not A Player"],
            "request-bulk-bad1",
            2,
        )

    assert path.read_bytes() == before
    assert DraftSession.load(path).current_pick == 2


def test_stale_bulk_and_stale_undo_leave_latest_pick_untouched(web_draft):
    path = web_draft["session"].path
    service = DraftMutationService(path)
    latest = DraftSession.load(path).active_selections()[-1]

    service.record_pick("Bijan", "request-pick-before-stale")

    with pytest.raises(StaleMutationError, match="bulk preview"):
        service.record_bulk(["Chase", "Bowers"], "request-stale-bulk", 2)
    with pytest.raises(StaleMutationError, match="undo confirmation"):
        service.undo(
            "request-stale-undo",
            expected_target_event_id=latest["id"],
        )

    current = DraftSession.load(path)
    assert current.current_pick == 3
    assert current.active_selections()[-1]["player"] == "Bijan Robinson"


def test_concurrent_bulk_double_tap_records_one_batch(web_draft):
    path = web_draft["session"].path

    def record():
        return DraftMutationService(path).record_bulk(
            ["Bijan", "Chase"],
            "request-bulk-double-tap",
            2,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: record(), range(2)))

    assert sorted(result["replayed"] for result in results) == [False, True]
    assert DraftSession.load(path).current_pick == 4


def test_concurrent_session_creation_is_idempotent(web_draft):
    path = web_draft["sessions_dir"] / "new-session.json"

    def create():
        return DraftSessionCreationService(path, web_draft["board_path"]).create(
            "new-session", 4, 2, 3, "request-create-double-tap"
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: create(), range(2)))

    assert sorted(result["replayed"] for result in results) == [False, True]
    assert DraftSession.load(path).user_team == 3

    with pytest.raises(SessionAlreadyExistsError):
        DraftSessionCreationService(path, web_draft["board_path"]).create(
            "new-session", 4, 2, 1, "different-create-request"
        )


def test_session_delete_moves_file_to_recoverable_trash_and_replays(web_draft):
    path = web_draft["session"].path
    service = DraftSessionDeletionService(path)

    deleted = service.delete("request-delete-session-0001")
    replay = DraftSessionDeletionService(path).delete("request-delete-session-0001")

    assert deleted == {
        "name": "phone-test",
        "deleted": True,
        "recoverable": True,
        "replayed": False,
    }
    assert replay["replayed"] is True
    assert not path.exists()
    archives = list((path.parent / ".trash").glob("phone-test.*.json"))
    assert len(archives) == 1
    archived = DraftSession.load(archives[0])
    assert archived.payload["session"]["deletion_request_id"] == "request-delete-session-0001"
    assert archived.current_pick == 2

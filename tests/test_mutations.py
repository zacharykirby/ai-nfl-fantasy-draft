from concurrent.futures import ThreadPoolExecutor

from fantasy_draft.draft.mutations import DraftMutationService
from fantasy_draft.draft.session import DraftSession


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

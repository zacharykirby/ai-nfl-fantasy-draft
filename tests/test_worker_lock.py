import pytest

from fantasy_draft.api.worker_lock import SessionWorkerLock


def test_sessions_directory_allows_only_one_server_process(tmp_path):
    first = SessionWorkerLock(tmp_path / "sessions")
    second = SessionWorkerLock(tmp_path / "sessions")
    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="exactly one server worker"):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()

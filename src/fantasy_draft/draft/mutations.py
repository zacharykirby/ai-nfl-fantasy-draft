"""Serialized, idempotent application services for draft state changes."""

from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Dict, Iterator

from fantasy_draft.draft.cockpit import DraftCockpitService
from fantasy_draft.draft.session import DraftSession, DraftSessionError


class IdempotencyConflictError(DraftSessionError):
    pass


class SessionMutationCoordinator:
    """Provide one in-process lock for each resolved session file."""

    def __init__(self):
        self._guard = Lock()
        self._locks: Dict[str, RLock] = {}

    @contextmanager
    def lock(self, path: Path) -> Iterator[None]:
        key = str(Path(path).resolve())
        with self._guard:
            session_lock = self._locks.setdefault(key, RLock())
        with session_lock:
            yield


COORDINATOR = SessionMutationCoordinator()


class DraftMutationService:
    def __init__(self, session_path: Path):
        self.session_path = Path(session_path)

    def record_pick(
        self,
        player: str,
        request_id: str,
        mode: str = "balanced",
    ) -> Dict[str, Any]:
        with COORDINATOR.lock(self.session_path):
            session = DraftSession.load(self.session_path)
            existing = self._event_for_request(session, request_id, "selection")
            if existing:
                return self._result(session, existing, mode, replayed=True)
            event = session.draft(player, request_id=request_id)
            return self._result(session, event, mode, replayed=False)

    def undo(self, request_id: str, mode: str = "balanced") -> Dict[str, Any]:
        with COORDINATOR.lock(self.session_path):
            session = DraftSession.load(self.session_path)
            existing = self._event_for_request(session, request_id, "undo")
            if existing:
                return self._result(session, existing, mode, replayed=True)
            event = session.undo(request_id=request_id)
            return self._result(session, event, mode, replayed=False)

    @staticmethod
    def _event_for_request(
        session: DraftSession,
        request_id: str,
        expected_type: str,
    ) -> Dict[str, Any]:
        event = next(
            (item for item in session.payload["events"] if item.get("request_id") == request_id),
            None,
        )
        if event and event.get("type") != expected_type:
            raise IdempotencyConflictError(
                "The request ID was already used for a different operation"
            )
        return event or {}

    @staticmethod
    def _result(
        session: DraftSession,
        event: Dict[str, Any],
        mode: str,
        replayed: bool,
    ) -> Dict[str, Any]:
        return {
            "event": event,
            "cockpit": DraftCockpitService(session).snapshot(mode=mode),
            "replayed": replayed,
        }

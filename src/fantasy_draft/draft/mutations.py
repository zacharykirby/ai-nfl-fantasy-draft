"""Serialized, idempotent application services for draft state changes."""

from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Dict, Iterator

from fantasy_draft.draft.cockpit import DraftCockpitService
from fantasy_draft.draft.session import DraftSession, DraftSessionError


class IdempotencyConflictError(DraftSessionError):
    pass


class StaleMutationError(DraftSessionError):
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

    def preview_bulk(self, players: list) -> Dict[str, Any]:
        if not 2 <= len(players) <= 20:
            raise DraftSessionError("Bulk catch-up requires between 2 and 20 players")
        with COORDINATOR.lock(self.session_path):
            source = DraftSession.load(self.session_path)
            session = DraftSession(deepcopy(source.payload), source.path)
            start_pick = session.current_pick
            events = [session.draft(player, persist=False) for player in players]
            return {
                "start_pick": start_pick,
                "end_pick": events[-1]["overall_pick"],
                "picks": events,
            }

    def record_bulk(
        self,
        players: list,
        request_id: str,
        expected_start_pick: int,
        mode: str = "balanced",
    ) -> Dict[str, Any]:
        if not 2 <= len(players) <= 20:
            raise DraftSessionError("Bulk catch-up requires between 2 and 20 players")
        with COORDINATOR.lock(self.session_path):
            session = DraftSession.load(self.session_path)
            existing = self._events_for_batch_request(session, request_id)
            if existing:
                return self._bulk_result(session, existing, mode, replayed=True)
            self._raise_if_request_used(session, request_id)
            if session.current_pick != expected_start_pick:
                raise StaleMutationError(
                    "Draft state changed after the bulk preview. Preview the picks again."
                )
            events = [
                session.draft(
                    player,
                    batch_request_id=request_id,
                    persist=False,
                )
                for player in players
            ]
            session.save()
            return self._bulk_result(session, events, mode, replayed=False)

    def undo(
        self,
        request_id: str,
        mode: str = "balanced",
        expected_target_event_id: str = "",
    ) -> Dict[str, Any]:
        with COORDINATOR.lock(self.session_path):
            session = DraftSession.load(self.session_path)
            existing = self._event_for_request(session, request_id, "undo")
            if existing:
                return self._result(session, existing, mode, replayed=True)
            selections = session.active_selections()
            if (
                expected_target_event_id
                and selections
                and selections[-1]["id"] != expected_target_event_id
            ):
                raise StaleMutationError(
                    "The latest pick changed after the undo confirmation. Refresh and try again."
                )
            event = session.undo(request_id=request_id)
            return self._result(session, event, mode, replayed=False)

    @staticmethod
    def _event_for_request(
        session: DraftSession,
        request_id: str,
        expected_type: str,
    ) -> Dict[str, Any]:
        batch = DraftMutationService._events_for_batch_request(session, request_id)
        if batch:
            raise IdempotencyConflictError(
                "The request ID was already used for a different operation"
            )
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
    def _events_for_batch_request(
        session: DraftSession, request_id: str
    ) -> list:
        return [
            item
            for item in session.payload["events"]
            if item.get("batch_request_id") == request_id
        ]

    @staticmethod
    def _raise_if_request_used(session: DraftSession, request_id: str) -> None:
        if any(item.get("request_id") == request_id for item in session.payload["events"]):
            raise IdempotencyConflictError(
                "The request ID was already used for a different operation"
            )

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

    @staticmethod
    def _bulk_result(
        session: DraftSession,
        events: list,
        mode: str,
        replayed: bool,
    ) -> Dict[str, Any]:
        return {
            "events": events,
            "cockpit": DraftCockpitService(session).snapshot(mode=mode),
            "replayed": replayed,
        }

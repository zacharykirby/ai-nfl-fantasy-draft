"""Serialized, idempotent application services for draft state changes."""

from copy import deepcopy
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Dict, Iterator

from fantasy_draft.draft.cockpit import DraftCockpitService
from fantasy_draft.draft.session import DraftSession, DraftSessionError, utc_now


class IdempotencyConflictError(DraftSessionError):
    pass


class StaleMutationError(DraftSessionError):
    pass


class SessionAlreadyExistsError(DraftSessionError):
    pass


class SessionDeletionNotFoundError(DraftSessionError):
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


class DraftSessionCreationService:
    def __init__(self, session_path: Path, board_path: Path):
        self.session_path = Path(session_path)
        self.board_path = Path(board_path)

    def create(
        self,
        name: str,
        league_size: int,
        rounds: int,
        user_team: int,
        request_id: str,
    ) -> Dict[str, Any]:
        with COORDINATOR.lock(self.session_path):
            if self.session_path.exists():
                session = DraftSession.load(self.session_path)
                if session.payload["session"].get("creation_request_id") == request_id:
                    return self._result(session, replayed=True)
                raise SessionAlreadyExistsError(
                    "A draft session named '{}' already exists".format(name)
                )
            session = DraftSession.create(
                self.session_path,
                self.board_path,
                name,
                league_size,
                rounds,
                user_team,
                request_id=request_id,
            )
            return self._result(session, replayed=False)

    @staticmethod
    def _result(session: DraftSession, replayed: bool) -> Dict[str, Any]:
        return {
            "session": session.summary(),
            "cockpit": DraftCockpitService(session).snapshot(),
            "replayed": replayed,
        }


class DraftSessionDeletionService:
    """Move an active session into a recoverable local trash directory."""

    def __init__(self, session_path: Path):
        self.session_path = Path(session_path)
        self.trash_dir = self.session_path.parent / ".trash"

    def delete(self, request_id: str) -> Dict[str, Any]:
        with COORDINATOR.lock(self.session_path):
            archive = self._archive_path(request_id)
            if not self.session_path.is_file():
                if archive.is_file():
                    return self._result(DraftSession.load(archive), replayed=True)
                raise SessionDeletionNotFoundError(
                    "Session not found: {}".format(self.session_path.stem)
                )

            if archive.exists():
                raise IdempotencyConflictError(
                    "The deletion request ID collides with an existing archive"
                )
            self.trash_dir.mkdir(parents=True, exist_ok=True)
            self.session_path.replace(archive)
            session = DraftSession.load(archive)
            session.payload["session"]["deletion_request_id"] = request_id
            session.payload["session"]["deleted_at"] = session.payload["session"].get(
                "deleted_at"
            ) or utc_now()
            session.save()
            return self._result(session, replayed=False)

    def _archive_path(self, request_id: str) -> Path:
        digest = sha256(request_id.encode("utf-8")).hexdigest()[:20]
        return self.trash_dir / "{}.{}.json".format(self.session_path.stem, digest)

    @staticmethod
    def _result(session: DraftSession, replayed: bool) -> Dict[str, Any]:
        return {
            "name": session.payload["session"]["name"],
            "deleted": True,
            "recoverable": True,
            "replayed": replayed,
        }


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

"""Filesystem-backed read access for draft sessions."""

import re
from pathlib import Path
from typing import List

from fantasy_draft.draft.session import DraftSession


SESSION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


class SessionNotFoundError(FileNotFoundError):
    pass


class BoardNotFoundError(FileNotFoundError):
    pass


class InvalidSessionNameError(ValueError):
    pass


class SessionRepository:
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = Path(sessions_dir)

    def paths(self) -> List[Path]:
        if not self.sessions_dir.exists():
            return []
        return sorted(self.sessions_dir.glob("*.json"))

    def count(self) -> int:
        return len(self.paths())

    def load(self, name: str) -> DraftSession:
        return DraftSession.load(self.path(name))

    def candidate_path(self, name: str) -> Path:
        if not SESSION_NAME_PATTERN.fullmatch(name):
            raise InvalidSessionNameError("Session name contains unsupported characters")
        return self.sessions_dir / "{}.json".format(name)

    def path(self, name: str) -> Path:
        path = self.candidate_path(name)
        if not path.is_file():
            raise SessionNotFoundError("Session not found: {}".format(name))
        return path

    def list(self) -> List[DraftSession]:
        return sorted(
            [DraftSession.load(path) for path in self.paths()],
            key=lambda session: session.payload["session"]["updated_at"],
            reverse=True,
        )

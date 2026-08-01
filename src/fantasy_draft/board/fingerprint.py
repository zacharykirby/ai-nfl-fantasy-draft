"""Stable identity for the exact board used by live and fallback workflows."""

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


FINGERPRINT_PREFIX = "sha256:"
FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CHEATSHEET_FINGERPRINT_PATTERN = re.compile(
    r"^- Board fingerprint: `(?P<fingerprint>sha256:[0-9a-f]{64})`$",
    re.MULTILINE,
)


def board_fingerprint(board: Dict[str, Any]) -> str:
    """Hash canonical board content while excluding the self-referential field."""
    canonical = copy.deepcopy(board)
    metadata = canonical.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("board_fingerprint", None)
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return FINGERPRINT_PREFIX + hashlib.sha256(encoded).hexdigest()


def stamp_board_fingerprint(board: Dict[str, Any]) -> str:
    """Set and return the canonical fingerprint for a mutable board payload."""
    metadata = board.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Board metadata must be an object")
    fingerprint = board_fingerprint(board)
    metadata["board_fingerprint"] = fingerprint
    return fingerprint


def verify_board_fingerprint(board: Dict[str, Any]) -> Dict[str, Any]:
    """Report whether the saved fingerprint matches the current board content."""
    metadata = board.get("metadata") or {}
    saved = metadata.get("board_fingerprint") if isinstance(metadata, dict) else None
    actual = board_fingerprint(board)
    matches = saved == actual and FINGERPRINT_PATTERN.match(str(saved)) is not None
    return {
        "status": "ready" if matches else "not_ready",
        "saved": saved,
        "actual": actual,
        "matches": matches,
    }


def cheatsheet_fingerprint(path: Path) -> Optional[str]:
    """Extract the exact-board fingerprint from a generated emergency sheet."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    match = CHEATSHEET_FINGERPRINT_PATTERN.search(text)
    return match.group("fingerprint") if match else None


def verify_fallback_fingerprint(board: Dict[str, Any], fallback_path: Path) -> Dict[str, Any]:
    """Report board and fallback agreement without changing either artifact."""
    board_report = verify_board_fingerprint(board)
    fallback = cheatsheet_fingerprint(fallback_path)
    matches = board_report["matches"] and fallback == board_report["actual"]
    return {
        "status": "ready" if matches else "not_ready",
        "matches": matches,
        "board": board_report,
        "fallback": fallback,
    }

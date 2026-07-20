"""Conservative natural-language interpretation for explicit draft commands."""

import re
from typing import List, Optional


PICK_PATTERNS = (
    re.compile(r"^(?:someone|they|team\s+\d+)?\s*(?:got|took|picked|drafted)\s+(.+?)$", re.I),
    re.compile(r"^(?:draft|pick|record)\s+(.+?)$", re.I),
    re.compile(r"^(.+?)\s+got\s+picked$", re.I),
    re.compile(r"^(.+?)\s+(?:was\s+)?(?:picked|drafted|taken)$", re.I),
    re.compile(r"^(.+?)\s+(?:is\s+)?gone$", re.I),
)


def pick_query(text: str) -> Optional[str]:
    """Extract a player query only from phrases that clearly describe a pick."""
    cleaned = re.sub(r"[.!?]+$", "", str(text or "").strip())
    for pattern in PICK_PATTERNS:
        match = pattern.fullmatch(cleaned)
        if match:
            query = match.group(1).strip(" ,:-")
            return query or None
    return None


def bulk_pick_queries(text: str) -> List[str]:
    """Extract ordered player queries from an explicit catch-up entry."""
    segments = re.split(r"[,;\n]+", str(text or ""))
    queries = []
    for segment in segments:
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", segment).strip()
        if not cleaned:
            continue
        queries.append(pick_query(cleaned) or cleaned.strip(" .!?"))
    return queries

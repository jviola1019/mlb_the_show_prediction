"""UUID parsing helpers shared by API, CLI, and React contracts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable


UUID_RE = re.compile(r"(?<![a-fA-F0-9])([a-fA-F0-9]{32})(?![a-fA-F0-9])")


@dataclass(frozen=True)
class UUIDParseResult:
    uuids: list[str]
    duplicates: list[str]
    invalid_tokens: list[str]
    raw_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def is_uuid(value: object) -> bool:
    return isinstance(value, str) and bool(UUID_RE.fullmatch(value.strip()))


def parse_uuid_tokens(text_or_values: str | Iterable[object] | None) -> UUIDParseResult:
    """Extract valid 32-hex UUIDs without mutating their order.

    Valid UUIDs are lowercased for API consistency. First-seen order is
    preserved. Duplicates are reported once, also in first duplicate order.
    """

    if text_or_values is None:
        return UUIDParseResult([], [], [], 0)
    if isinstance(text_or_values, str):
        text = text_or_values
        raw_tokens = [tok for tok in re.split(r"[\s,;|\"'<>()[\]{}]+", text) if tok]
    else:
        raw_tokens = [str(v).strip() for v in text_or_values if str(v).strip()]
        text = "\n".join(raw_tokens)

    seen: set[str] = set()
    dup_seen: set[str] = set()
    uuids: list[str] = []
    duplicates: list[str] = []
    for match in UUID_RE.finditer(text):
        uuid = match.group(1).lower()
        if uuid in seen:
            if uuid not in dup_seen:
                duplicates.append(uuid)
                dup_seen.add(uuid)
            continue
        seen.add(uuid)
        uuids.append(uuid)

    invalid_tokens: list[str] = []
    for token in raw_tokens:
        if UUID_RE.fullmatch(token):
            continue
        if len(token) >= 8 and re.search(r"[A-Za-z0-9]", token):
            invalid_tokens.append(token)

    return UUIDParseResult(uuids, duplicates, invalid_tokens, len(raw_tokens))

from __future__ import annotations

from collections.abc import Iterable

from .models import Business


def filter_new(incoming: Iterable[Business], existing_keys: set[str]) -> list[Business]:
    """Return businesses whose dedup keys don't intersect existing_keys.
    Also dedupes within the incoming batch itself (first occurrence wins).
    A business with no dedup keys is always treated as new."""
    seen = set(existing_keys)
    result: list[Business] = []
    for b in incoming:
        keys = b.dedup_keys()
        if keys and keys & seen:
            continue
        result.append(b)
        seen.update(keys)
    return result

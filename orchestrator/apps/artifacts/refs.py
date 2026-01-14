from __future__ import annotations

import re
import uuid
from typing import Any


_ARTIFACT_URI_PREFIX = "artifact://artifacts/"
_ARTIFACT_ID_RE = re.compile(
    r"artifact://artifacts/(?P<id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
    re.IGNORECASE,
)


def contains_artifact_ref(value: Any, artifact_id: uuid.UUID) -> bool:
    needle = f"{_ARTIFACT_URI_PREFIX}{artifact_id}".lower()
    if not needle:
        return False

    stack = [value]
    while stack:
        cur = stack.pop()
        if cur is None:
            continue

        if isinstance(cur, str):
            if needle in cur.lower():
                return True
            continue

        if isinstance(cur, dict):
            stack.extend(cur.values())
            continue

        if isinstance(cur, (list, tuple)):
            stack.extend(cur)
            continue

    return False


def extract_artifact_ids(value: Any) -> set[uuid.UUID]:
    found: set[uuid.UUID] = set()
    stack = [value]
    while stack:
        cur = stack.pop()
        if cur is None:
            continue

        if isinstance(cur, str):
            for match in _ARTIFACT_ID_RE.finditer(cur):
                raw = match.group("id")
                try:
                    found.add(uuid.UUID(raw))
                except ValueError:
                    continue
            continue

        if isinstance(cur, dict):
            stack.extend(cur.values())
            continue

        if isinstance(cur, (list, tuple)):
            stack.extend(cur)
            continue

    return found


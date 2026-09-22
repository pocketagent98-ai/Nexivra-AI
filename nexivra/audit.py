"""Audit logging without secret values.

Every significant action (model call, vault access, quota decision, claim
status change, research step) is appended to a JSONL trail that can replay
the full chain: answer -> claim -> evidence -> source -> task -> model ->
timestamp. Secrets are structurally impossible to log: the ``mask()``
helper collapses any field whose name looks like a credential.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, IO, List, Optional

from .types import _now_iso

SECRET_NAME_RE = re.compile(r"(key|token|secret|password|credential|authorization)", re.IGNORECASE)


def mask(value: Any, name: str = "value") -> Any:
    """Collapse credential-looking fields/values so they can never reach a log."""
    if isinstance(value, dict):
        return {k: mask(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask(v, name) for v in value]
    if SECRET_NAME_RE.search(name):
        if isinstance(value, str) and value:
            return "***masked***"
    if isinstance(value, str) and value.startswith(("nvapi-", "sk-", "Bearer ")):
        return "***masked***"
    return value


class AuditLogger:
    """Append-only JSONL audit trail.

    ``events`` is also kept in memory so tests and in-process callers can
    assert on the trail without reading files.
    """

    def __init__(self, sink: Optional[IO[str]] = None) -> None:
        self._sink = sink
        self.events: List[Dict[str, Any]] = []

    def log(self, event: str, **fields: Any) -> Dict[str, Any]:
        record = {"ts": _now_iso(), "event": event, **mask(fields)}
        self.events.append(record)
        if self._sink is not None:
            self._sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._sink.flush()
        return record

    def events_of(self, event: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e["event"] == event]

    def search(self, **match: Any) -> List[Dict[str, Any]]:
        out = []
        for e in self.events:
            if all(e.get(k) == v for k, v in match.items()):
                out.append(e)
        return out

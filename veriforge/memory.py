"""ResearchMemory — project memory across research runs.

Stores compact run summaries (question, claim statuses, source urls) per
project so later runs can recall what was already verified, avoid
re-research, and keep sources consistent. Bodies and secrets are never
stored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import _now_iso


def _keywords(text: str, limit: int = 20) -> List[str]:
    words = [w.strip(".,:;!?()[]").lower() for w in text.split()]
    return [w for w in words if len(w) > 3][:limit]


class ResearchMemory:
    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path else None
        self._projects: Dict[str, List[Dict[str, Any]]] = {}
        if self._path and self._path.exists():
            try:
                self._projects = json.loads(self._path.read_text() or "{}")
            except json.JSONDecodeError:
                self._projects = {}

    def remember(self, project: str, question: str, report: Any) -> Dict[str, Any]:
        entry = {
            "at": _now_iso(),
            "question": question,
            "mode": getattr(report, "mode", None),
            "statuses": getattr(report, "status_counts", {}) if hasattr(report, "status_counts") else {},
            "source_urls": [s.get("url") for s in (report.to_dict().get("sources", []) if hasattr(report, "to_dict") else [])],
        }
        self._projects.setdefault(project, []).append(entry)
        self._flush()
        return entry

    def recall(self, question: str, project: Optional[str] = None, *, limit: int = 5) -> List[Dict[str, Any]]:
        """Return previous run summaries whose question overlaps this one."""
        kws = set(_keywords(question))
        pool: List[Dict[str, Any]] = []
        if project and project in self._projects:
            pool = self._projects[project]
        else:
            for runs in self._projects.values():
                pool.extend(runs)
        scored = []
        for entry in pool:
            other = set(_keywords(entry.get("question", "")))
            overlap = len(kws & other)
            if overlap >= 2:
                scored.append((overlap, entry))
        scored.sort(key=lambda t: -t[0])
        return [e for _, e in scored[:limit]]

    def projects(self) -> List[str]:
        return list(self._projects)

    def _flush(self) -> None:
        if self._path:
            self._path.write_text(json.dumps(self._projects, indent=2))

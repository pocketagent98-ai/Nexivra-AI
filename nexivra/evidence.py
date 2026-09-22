"""Evidence layer: SourceRegistry + EvidenceStore.

A source is tracked with URL, title, domain, publication date, access
date, type and optional content hash. Evidence is an excerpt extracted
from exactly one source. Sources are de-duplicated by content hash so the
same page retrieved through two search engines is one source, twice
accessed.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .types import Claim, Evidence, Source, SourceTier, content_hash, new_id


class RegistryError(ValueError):
    pass


class SourceRegistry:
    """Tracks every source used in a research run (and optionally persists)."""

    def __init__(self) -> None:
        self._by_id: Dict[str, Source] = {}
        self._by_url: Dict[str, str] = {}

    def add(
        self,
        url: str,
        title: str,
        *,
        domain: Optional[str] = None,
        source_type: str = "web",
        tier: int = SourceTier.REPUTABLE_SECONDARY,
        published_at: Optional[str] = None,
        is_snippet: bool = False,
        body: Optional[str] = None,
    ) -> Source:
        if not url or not title:
            raise RegistryError("source needs url and title")
        if url in self._by_url:
            return self._by_id[self._by_url[url]]
        src = Source(
            id=new_id("src"),
            url=url,
            title=title,
            domain=domain or url.split("/")[2] if "://" in url else domain or url,
            source_type=source_type,
            tier=int(tier),
            published_at=published_at,
            is_snippet=is_snippet,
            content_hash=content_hash(body) if body else None,
        )
        self._by_id[src.id] = src
        self._by_url[url] = src.id
        return src

    def get(self, source_id: str) -> Source:
        try:
            return self._by_id[source_id]
        except KeyError as exc:
            raise RegistryError(f"unknown source: {source_id}") from exc

    def find_by_url(self, url: str) -> Optional[Source]:
        sid = self._by_url.get(url)
        return self._by_id[sid] if sid else None

    def dedupe_body(self, body: str) -> bool:
        """Return True when a source with this body hash already exists."""
        h = content_hash(body)
        return any(s.content_hash == h for s in self._by_id.values())

    def all(self) -> List[Source]:
        return list(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)


class EvidenceStore:
    """All evidence excerpts, linked to their source and optionally to the
    research task that produced them."""

    def __init__(self) -> None:
        self._by_id: Dict[str, Evidence] = {}
        self._by_source: Dict[str, List[str]] = {}

    def add(
        self,
        source_id: str,
        excerpt: str,
        *,
        quote: Optional[str] = None,
        task_id: Optional[str] = None,
        measurements: Optional[List[Dict]] = None,
    ) -> Evidence:
        if not excerpt or not excerpt.strip():
            raise RegistryError("evidence excerpt must be non-empty")
        ev = Evidence(
            id=new_id("ev"),
            source_id=source_id,
            excerpt=excerpt.strip(),
            quote=quote,
            task_id=task_id,
            measurements=measurements or [],
        )
        self._by_id[ev.id] = ev
        self._by_source.setdefault(source_id, []).append(ev.id)
        return ev

    def get(self, evidence_id: str) -> Evidence:
        try:
            return self._by_id[evidence_id]
        except KeyError as exc:
            raise RegistryError(f"unknown evidence: {evidence_id}") from exc

    def for_claim(self, claim: Claim) -> List[Evidence]:
        return [self._by_id[c] for c in claim.sources if c in self._by_id]

    def by_source(self, source_id: str) -> List[Evidence]:
        return [self._by_id[i] for i in self._by_source.get(source_id, [])]

    def all(self) -> List[Evidence]:
        return list(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

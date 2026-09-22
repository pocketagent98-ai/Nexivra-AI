"""Core data types for the VeriForge evidence pipeline.

Everything important in a research run is represented as a traceable record:

    Answer -> Claim -> Evidence -> Source -> Research task -> Provider/model

All records are JSON-serialisable dataclasses so that stores can persist
them and the audit logger can replay a full chain without ambiguity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return utcnow().isoformat()


class ClaimStatus(str, Enum):
    """Allowed support statuses. Uncertainty is never converted into fake
    certainty: 'unverified' stays 'unverified'."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"
    OUTDATED = "outdated"
    OPINION = "opinion"
    INFERENCE = "inference"


class SourceTier(int, Enum):
    """Source-quality preference order (1 = best)."""

    OFFICIAL_PRIMARY = 1
    GOVERNMENT_INSTITUTIONAL = 2
    ACADEMIC = 3
    COMPANY_DOCUMENTATION = 4
    REPUTABLE_SECONDARY = 5
    COMMUNITY = 6

    @classmethod
    def label(cls, tier: "SourceTier") -> str:
        return {
            cls.OFFICIAL_PRIMARY: "official/primary",
            cls.GOVERNMENT_INSTITUTIONAL: "government/institutional",
            cls.ACADEMIC: "academic",
            cls.COMPANY_DOCUMENTATION: "company documentation",
            cls.REPUTABLE_SECONDARY: "reputable secondary reporting",
            cls.COMMUNITY: "community material",
        }[tier]


@dataclass
class Source:
    """A retrieved source. A search snippet is NOT final evidence when the
    original page is available; `is_snippet` marks that distinction."""

    id: str
    url: str
    title: str
    domain: str
    source_type: str = "web"
    tier: int = SourceTier.REPUTABLE_SECONDARY
    published_at: Optional[str] = None
    accessed_at: str = field(default_factory=_now_iso)
    content_hash: Optional[str] = None
    is_snippet: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    """An extracted piece of evidence tied to exactly one source."""

    id: str
    source_id: str
    excerpt: str
    quote: Optional[str] = None
    retrieved_at: str = field(default_factory=_now_iso)
    task_id: Optional[str] = None
    # Numeric values extracted from the excerpt, used by the conflict
    # detector. Each entry: {"value": 50.0, "unit": "M", "context": "..."}
    measurements: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Claim:
    """A discrete factual claim extracted from research or synthesis."""

    id: str
    text: str
    sources: List[str] = field(default_factory=list)
    support_status: str = ClaimStatus.UNVERIFIED.value
    conflict_status: str = "none"
    freshness: str = "unknown"
    verification_notes: str = ""
    measurements: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    research_task_id: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.support_status in (
            ClaimStatus.SUPPORTED.value,
            ClaimStatus.PARTIALLY_SUPPORTED.value,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def content_hash(text: str) -> str:
    """Stable SHA-256 hash used to detect duplicate/fetched-twice content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    """Short, collision-safe-enough id for one run; stores guarantee
    uniqueness by rejecting duplicates."""
    return f"{prefix}_{content_hash(utcnow().isoformat() + prefix + str(id(object())))[:12]}"

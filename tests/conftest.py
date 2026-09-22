"""Shared fixtures for the offline test suite. No network, no API keys."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from nexivra.adapters import AdapterError, ChatResult, StaticAdapter
from nexivra.audit import AuditLogger
from nexivra.claims import ClaimRegistry
from nexivra.conflicts import ContradictionDetector
from nexivra.evidence import EvidenceStore, SourceRegistry
from nexivra.gateway import ModelProfile, UniversalModelGateway
from nexivra.quotas import ModelBudget, QuotaGovernor
from nexivra.research import FetchTool, SearchHit, SearchTool
from nexivra.verify import VerificationEngine


class CannedSearch(SearchTool):
    def __init__(self, index: dict[str, list[SearchHit]] | None = None,
                 default: list[SearchHit] | None = None, fail_queries: set[str] | None = None):
        self.index = index or {}
        self.default = default or []
        self.fail_queries = fail_queries or set()
        self.queries: list[str] = []

    async def search(self, query: str) -> list[SearchHit]:
        self.queries.append(query)
        if query in self.fail_queries:
            raise RuntimeError("search backend down")
        for key, hits in self.index.items():
            if key in query:
                return hits
        return self.default


class CannedFetch(FetchTool):
    def __init__(self, bodies: dict[str, str]):
        self.bodies = bodies

    async def fetch(self, url: str) -> str:
        if url not in self.bodies:
            from nexivra.research import FetchError
            raise FetchError(f"404 not found: {url}")
        return self.bodies[url]


class FailingAdapter:
    """Always raises a retryable AdapterError — used to prove fallback."""

    name = "failing"

    def models(self, api_key):
        raise AdapterError("boom", status=503, retryable=True)

    def chat(self, model, messages, api_key, **kwargs):
        raise AdapterError("boom", status=429, retryable=True)

    def health(self, api_key):
        return {"provider": self.name, "status": "error"}


def build_gateway(script=None, default="TASK: placeholder", failing_first=False):
    audit = AuditLogger()
    quotas = QuotaGovernor(audit=audit)
    gw = UniversalModelGateway(quotas=quotas, audit=audit)
    if failing_first:
        gw.register_adapter(FailingAdapter())
        gw.add_profile(ModelProfile(provider="failing", model="f-1", priority=1))
    gw.register_adapter(StaticAdapter(name="static", script=script or {}, default=default))
    gw.add_profile(ModelProfile(provider="static", model="static-1", priority=10))
    return gw, audit, quotas


def build_verifier():
    sources = SourceRegistry()
    evidence = EvidenceStore()
    claims = ClaimRegistry()
    audit = AuditLogger()
    verifier = VerificationEngine(
        sources, evidence, claims, ContradictionDetector(), audit=audit, freshness_years=3.0
    )
    return sources, evidence, claims, verifier, audit


@pytest.fixture
def verifier_stack():
    return build_verifier()

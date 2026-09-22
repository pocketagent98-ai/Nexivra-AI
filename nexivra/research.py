"""ResearchEngine — the ASK -> PLAN -> RESEARCH -> COLLECT EVIDENCE ->
CROSS-CHECK -> VERIFY -> SYNTHESIZE -> ACT pipeline.

Modes (build spec section 14):
- QUICK: small budget, fast response
- DEEP: multiple researchers, wider source coverage
- VERIFIED_DEEP: + claim verification + contradiction checks (default here)
- AUTONOMOUS: long-running but bounded
- RESEARCH_TO_ACTION: research first, then execute only approved actions

Every run is bounded (max_agents / max_steps / max_searches / wall time /
output tokens). More agents are not automatically better: the evidence
pipeline must be correct first.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Sequence

from .adapters import ChatMessage
from .audit import AuditLogger
from .claims import ClaimRegistry
from .conflicts import extract_measurements
from .evidence import EvidenceStore, SourceRegistry
from .gateway import UniversalModelGateway
from .memory import ResearchMemory
from .quotas import QuotaGovernor
from .ssrf import UnsafeUrlError, assert_safe_url
from .types import ClaimStatus, SourceTier
from .untrusted import FENCE_CLOSE, FENCE_OPEN, defuse
from .verify import VerificationEngine


class ResearchMode(str, Enum):
    QUICK = "quick"
    DEEP = "deep"
    VERIFIED_DEEP = "verified_deep"
    AUTONOMOUS = "autonomous"
    RESEARCH_TO_ACTION = "research_to_action"


@dataclass
class RunLimits:
    max_agents: int = 12
    max_steps: int = 500
    max_searches: int = 100
    max_wall_time_seconds: float = 1800.0
    max_output_tokens: int = 30000

    @classmethod
    def for_mode(cls, mode: ResearchMode) -> "RunLimits":
        base = cls()
        if mode == ResearchMode.QUICK:
            return cls(max_agents=2, max_steps=20, max_searches=3,
                       max_wall_time_seconds=120.0, max_output_tokens=2000)
        if mode == ResearchMode.DEEP:
            return cls(max_agents=6, max_steps=150, max_searches=30,
                       max_wall_time_seconds=900.0, max_output_tokens=20000)
        if mode == ResearchMode.VERIFIED_DEEP:
            return cls(max_agents=8, max_steps=200, max_searches=40,
                       max_wall_time_seconds=1200.0, max_output_tokens=25000)
        if mode == ResearchMode.AUTONOMOUS:
            return cls(max_agents=12, max_steps=500, max_searches=100,
                       max_wall_time_seconds=1800.0, max_output_tokens=30000)
        return base  # RESEARCH_TO_ACTION


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str
    published_at: Optional[str] = None
    tier: int = SourceTier.REPUTABLE_SECONDARY


class SearchTool(Protocol):
    async def search(self, query: str) -> List[SearchHit]: ...


class FetchTool(Protocol):
    async def fetch(self, url: str) -> str: ...


class FetchError(RuntimeError):
    pass


@dataclass
class _Task:
    id: str
    description: str
    role: str = "researcher"
    agent: str = "researcher-1"


@dataclass
class ResearchReport:
    question: str
    mode: str
    plan: List[Dict[str, str]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    claims: List[Dict[str, Any]] = field(default_factory=list)
    verification: Dict[str, Any] = field(default_factory=dict)
    synthesis: str = ""
    tool_failures: List[str] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    truncated: bool = False
    executed_actions: List[str] = field(default_factory=list)

    @property
    def status_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for c in self.claims:
            out[c["support_status"]] = out.get(c["support_status"], 0) + 1
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "mode": self.mode,
            "plan": self.plan,
            "sources": self.sources,
            "claims": self.claims,
            "verification": self.verification,
            "synthesis": self.synthesis,
            "tool_failures": self.tool_failures,
            "usage": self.usage,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "truncated": self.truncated,
            "executed_actions": self.executed_actions,
        }


class ResearchEngine:
    def __init__(
        self,
        *,
        gateway: UniversalModelGateway,
        search_tool: SearchTool,
        fetch_tool: FetchTool,
        source_registry: Optional[SourceRegistry] = None,
        evidence_store: Optional[EvidenceStore] = None,
        claim_registry: Optional[ClaimRegistry] = None,
        verifier: Optional[VerificationEngine] = None,
        audit: Optional[AuditLogger] = None,
        memory: Optional[ResearchMemory] = None,
        mode: ResearchMode = ResearchMode.VERIFIED_DEEP,
        limits: Optional[RunLimits] = None,
        max_parallel: int = 4,
        approved_actions: Optional[Sequence[str]] = None,
    ) -> None:
        self.gateway = gateway
        self.search_tool = search_tool
        self.fetch_tool = fetch_tool
        self.sources = source_registry or SourceRegistry()
        self.evidence = evidence_store or EvidenceStore()
        self.claims = claim_registry or ClaimRegistry()
        self.audit = audit or AuditLogger()
        self.verifier = verifier or VerificationEngine(
            self.sources, self.evidence, self.claims, audit=self.audit
        )
        self.memory = memory
        self.mode = mode
        self.limits = limits or RunLimits.for_mode(mode)
        self.max_parallel = min(max_parallel, max(1, self.limits.max_agents))
        self.approved_actions = list(approved_actions or [])
        self._steps = 0
        self._searches = 0

    # -- helpers -------------------------------------------------------------

    def _tick(self, started: float) -> bool:
        """Return False when the wall-time budget is exhausted."""
        return (time.monotonic() - started) < self.limits.max_wall_time_seconds

    def _step(self) -> bool:
        self._steps += 1
        return self._steps <= self.limits.max_steps

    async def _search(self, query: str) -> List[SearchHit]:
        if self._searches >= self.limits.max_searches:
            return []
        self._searches += 1
        try:
            return await self.search_tool.search(query)
        except Exception as exc:
            self.audit.log("tool.search_failed", query=query, detail=str(exc)[:200])
            raise

    async def _fetch(self, url: str) -> str:
        assert_safe_url(url, resolve_dns=False)  # strict mode resolved at the real fetch layer
        return await self.fetch_tool.fetch(url)

    # -- pipeline --------------------------------------------------------------

    async def run(self, question: str, *, project: Optional[str] = None) -> ResearchReport:
        started = time.monotonic()
        report = ResearchReport(question=question, mode=self.mode.value)
        self._steps, self._searches = 0, 0

        if self.memory:
            prior = self.memory.recall(question, project)
            if prior:
                report.plan.append({"id": "memory", "description": f"Reusing context from {len(prior)} prior run(s)"})

        # PLAN ---------------------------------------------------------------
        tasks = await self._plan(question)
        report.plan = [{"id": t.id, "description": t.description, "role": t.role} for t in tasks]

        # RESEARCH + COLLECT EVIDENCE -----------------------------------------
        tool_failures: List[str] = []
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def research(task: _Task) -> None:
            if not self._tick(started) or not self._step():
                return
            async with semaphore:
                try:
                    hits = await self._search(task.description)
                except Exception as exc:
                    tool_failures.append(f"search failed for {task.description!r}: {exc}")
                    return
                for hit in hits:
                    if not self._tick(started):
                        return
                    try:
                        raw = await self._fetch(hit.url)
                    except FetchError as exc:
                        tool_failures.append(f"fetch failed for {hit.url}: {exc}")
                        continue
                    except UnsafeUrlError as exc:
                        tool_failures.append(f"blocked unsafe url {hit.url}: {exc}")
                        continue
                    # retrieved content is untrusted data: neutralize + fence it
                    # before anything downstream sees it
                    body = defuse(raw)
                    src = self.sources.add(
                        hit.url, hit.title,
                        published_at=hit.published_at, tier=hit.tier,
                        is_snippet=False, body=body,
                    )
                    for sentence in _split_sentences(
                        body.replace(FENCE_OPEN, "").replace(FENCE_CLOSE, "")
                    ):
                        measurements = extract_measurements(sentence)
                        if not measurements:
                            continue
                        self.evidence.add(
                            src.id, sentence, task_id=task.id, measurements=measurements,
                        )

        await asyncio.gather(*(research(t) for t in tasks))

        # CROSS-CHECK: claim extraction with corroboration merging.
        # Two evidence records that talk about the same metric (same unit
        # family) become ONE claim so the verifier can see corroboration —
        # or contradiction — instead of two isolated half-claims.
        merged: List[Any] = []
        for ev in self.evidence.all():
            target = next(
                (c for c in merged if _shares_metric(c.measurements, ev.measurements)),
                None,
            )
            if target is not None:
                if ev.id not in target.sources:
                    target.sources.append(ev.id)
            else:
                claim = self.claims.register(
                    ev.excerpt, sources=[ev.id], research_task_id=ev.task_id,
                )
                claim.measurements = list(ev.measurements or [])
                merged.append(claim)

        # VERIFY ---------------------------------------------------------------
        draft = self._draft_synthesis()
        verification = self.verifier.verify_run(draft, self.claims.all(), tool_failures=tool_failures)
        report.claims = [cv.to_dict() for cv in verification.claim_verifications]
        report.verification = {
            "passed": verification.passed,
            "summary": verification.summary(),
            "gate_log": verification.gate_log,
            "tool_failures": verification.tool_failures,
            "unsupported_in_synthesis": verification.unsupported_in_synthesis,
        }

        # SYNTHESIZE -------------------------------------------------------------
        report.synthesis = await self._synthesize(question)
        report.tool_failures = tool_failures
        report.sources = [s.to_dict() for s in self.sources.all()]
        report.usage = self.gateway.quotas.usage()
        report.elapsed_seconds = time.monotonic() - started
        report.truncated = not self._tick(started)

        # ACT (only approved actions) ----------------------------------------------
        if self.mode == ResearchMode.RESEARCH_TO_ACTION:
            report.executed_actions = [
                a for a in self.approved_actions
                if verification.passed or a.startswith("disclose:")
            ]

        if self.memory and project:
            self.memory.remember(project, question, report)

        self.audit.log("research.done", mode=self.mode.value, steps=self._steps,
                       searches=self._searches, claims=len(report.claims),
                       truncated=report.truncated)
        return report

    # -- planning -----------------------------------------------------------

    async def _plan(self, question: str) -> List[_Task]:
        roles = ["researcher", "source_analyst", "claim_analyst", "contradiction_analyst"]
        prompt = (
            "You are the planner of an evidence-first research system. Break the "
            f"following question into up to {min(self.limits.max_agents, 4)} focused "
            "research tasks, one per line, format: TASK: <description>\n\n"
            f"Question: {question}"
        )
        try:
            result = await self.gateway.chat(
                [ChatMessage(role="user", content=prompt)], task="plan",
                max_tokens=min(1024, self.limits.max_output_tokens),
            )
            tasks = []
            for i, line in enumerate(result.text.splitlines()):
                line = line.strip()
                if line.upper().startswith("TASK:"):
                    desc = line[5:].strip() or line
                    tasks.append(_Task(
                        id=f"task_{i + 1}", description=desc,
                        role=roles[i % len(roles)], agent=f"agent_{i % self.max_parallel + 1}",
                    ))
            if tasks:
                return tasks[: self.limits.max_agents]
        except Exception as exc:
            self.audit.log("plan.fallback", detail=str(exc)[:200])
        return [_Task(id="task_1", description=question, role="researcher", agent="agent_1")]

    # -- synthesis ------------------------------------------------------------

    def _draft_synthesis(self) -> str:
        parts = [c.text for c in self.claims.all()]
        return " ".join(parts)

    async def _synthesize(self, question: str) -> str:
        """Deterministic, evidence-anchored synthesis. Claims are only stated
        with their verification status; conflicts are disclosed, never
        silently resolved; uncertainty is never converted into fake certainty."""
        claims = self.claims.all()
        lines: List[str] = [f"Research findings for: {question}", ""]

        supported = [c for c in claims if c.support_status == ClaimStatus.SUPPORTED.value]
        partial = [c for c in claims if c.support_status == ClaimStatus.PARTIALLY_SUPPORTED.value]
        conflicting = [c for c in claims if c.support_status == ClaimStatus.CONFLICTING.value]
        other = [c for c in claims if c.support_status in (
            ClaimStatus.UNVERIFIED.value, ClaimStatus.OUTDATED.value,
            ClaimStatus.OPINION.value, ClaimStatus.INFERENCE.value)]

        if supported:
            lines.append("Verified findings:")
            for c in supported:
                domains = self._domains_of(c)
                lines.append(f"- {c.text} (sources: {', '.join(domains) or 'n/a'})")
        if partial:
            lines.append("")
            lines.append("Findings supported by a single source (treat with caution):")
            for c in partial:
                lines.append(f"- {c.text} (source: {', '.join(self._domains_of(c)) or 'n/a'})")
        if conflicting:
            lines.append("")
            lines.append("CONFLICTING EVIDENCE — figures disagree between sources:")
            for c in conflicting:
                lines.append(f"- {c.text}")
                if c.verification_notes:
                    for note in c.verification_notes.splitlines():
                        lines.append(f"    {note}")
        if other:
            lines.append("")
            lines.append("Not fully verified (disclosed, not asserted as fact):")
            for c in other:
                lines.append(f"- {c.text} [{c.support_status}]")
        if not claims:
            lines.append("No verifiable evidence was collected for this question.")
        return "\n".join(lines)

    def _domains_of(self, claim: Any) -> List[str]:
        out = []
        for ev in self.evidence.for_claim(claim):
            try:
                out.append(self.sources.get(ev.source_id).domain)
            except Exception:
                pass
        return out


def _shares_metric(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    """True when both measurement lists mention the same unit family (e.g.
    two revenue figures in millions), regardless of the value — conflicting
    values must land on the SAME claim so the detector can see them."""
    def comparable(ms: List[Dict[str, Any]]) -> set:
        out = set()
        for m in ms or []:
            fam = str(m.get("family", "raw"))
            unit = str(m.get("unit") or "").lower()
            if fam in ("raw", "time", ""):
                continue
            out.add((fam, unit))
        return out

    return bool(comparable(a) & comparable(b))


def _split_sentences(text: str) -> List[str]:
    import re
    parts = re.split(r"(?<=[.!?])\s+", text or "")
    return [p.strip() for p in parts if len(p.strip()) > 15]

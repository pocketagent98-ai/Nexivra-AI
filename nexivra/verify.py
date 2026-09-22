"""Verification gate (build spec section 7).

Before any final research report is returned:

    Every major claim has evidence?   no  -> mark unverified / revise
    Conflicting sources?              yes -> explain the conflict
    Fresh enough?                     no  -> mark outdated/uncertain
    Synthesis introduced unsupported claims?  yes -> rewrite
    Tool failure?                     yes -> disclose limitation
    Then -> FINAL

The audit trail keeps the full chain for every claim:
answer section -> claim -> evidence -> source -> research task ->
model/provider -> timestamp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .claims import ClaimRegistry
from .conflicts import ContradictionDetector, ConflictReport
from .evidence import EvidenceStore, SourceRegistry
from .types import Claim, ClaimStatus, Source

from .audit import AuditLogger

_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> List[str]:
    """Lowercased word list, stop-worded — used to check whether a sentence
    in the synthesized answer corresponds to a registered claim."""
    stop = {
        "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "was",
        "were", "be", "been", "it", "its", "that", "this", "for", "on", "as",
        "by", "with", "at", "from", "has", "have", "had", "than", "then",
        "their", "there", "which", "will", "would", "can", "could", "about",
    }
    return [w for w in _WORD_RE.findall(text.lower()) if w not in stop]


@dataclass
class ClaimVerification:
    claim_id: str
    text: str
    support_status: str
    conflict_status: str
    freshness: str
    evidence_count: int
    source_domains: List[str]
    notes: str = ""
    conflict: Optional[ConflictReport] = None

    def to_dict(self) -> Dict[str, object]:
        d = {
            "claim_id": self.claim_id,
            "text": self.text,
            "support_status": self.support_status,
            "conflict_status": self.conflict_status,
            "freshness": self.freshness,
            "evidence_count": self.evidence_count,
            "source_domains": self.source_domains,
            "notes": self.notes,
        }
        if self.conflict is not None:
            d["conflict"] = self.conflict.to_dict()
        return d


@dataclass
class VerificationReport:
    passed: bool = False
    claim_verifications: List[ClaimVerification] = field(default_factory=list)
    unsupported_in_synthesis: List[str] = field(default_factory=list)
    tool_failures: List[str] = field(default_factory=list)
    gate_log: List[str] = field(default_factory=list)

    @property
    def status_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for cv in self.claim_verifications:
            out[cv.support_status] = out.get(cv.support_status, 0) + 1
        return out

    def summary(self) -> str:
        counts = ", ".join(f"{k}={v}" for k, v in sorted(self.status_counts.items()))
        bits = [f"claims: {counts or 'none'}"]
        if self.unsupported_in_synthesis:
            bits.append(f"unsupported-in-synthesis: {len(self.unsupported_in_synthesis)}")
        if self.tool_failures:
            bits.append(f"tool-failures: {len(self.tool_failures)}")
        return "; ".join(bits)


class VerificationEngine:
    def __init__(
        self,
        source_registry: SourceRegistry,
        evidence_store: EvidenceStore,
        claim_registry: ClaimRegistry,
        detector: Optional[ContradictionDetector] = None,
        *,
        audit: Optional[AuditLogger] = None,
        freshness_years: float = 3.0,
    ) -> None:
        self.sources = source_registry
        self.evidence = evidence_store
        self.claims = claim_registry
        self.detector = detector or ContradictionDetector()
        self.audit = audit
        self.freshness_years = freshness_years

    # -- single claim -------------------------------------------------------

    def check_claim(self, claim: Claim) -> ClaimVerification:
        evidence = [e for e in self.evidence.for_claim(claim)]
        src_domains: List[str] = []
        for ev in evidence:
            try:
                src_domains.append(self.sources.get(ev.source_id).domain)
            except Exception:
                pass

        # 1. every major claim needs evidence
        if not evidence:
            self.claims.update(claim.id, support_status=ClaimStatus.UNVERIFIED.value,
                               verification_notes="No evidence attached.")
            self._log(claim, "unverified", "no evidence")
            return ClaimVerification(claim.id, claim.text, ClaimStatus.UNVERIFIED.value,
                                     "none", "unknown", 0, [], notes="No evidence attached.")

        # 2. conflict check
        conflict = self.detector.check(claim, evidence, self.sources.all())
        if conflict.has_conflict:
            self.claims.update(
                claim.id, support_status=ClaimStatus.CONFLICTING.value,
                conflict_status="conflict", verification_notes=conflict.explanation,
            )
            self._log(claim, "conflicting", conflict.detail)
            return ClaimVerification(
                claim.id, claim.text, ClaimStatus.CONFLICTING.value, "conflict",
                "recent", len(evidence), src_domains,
                notes=conflict.explanation, conflict=conflict,
            )

        # 3. freshness
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        freshness = "recent"
        for ev in evidence:
            try:
                src = self.sources.get(ev.source_id)
            except Exception:
                continue
            if src.published_at:
                try:
                    published = datetime.fromisoformat(src.published_at.replace("Z", "+00:00"))
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                    age_years = (now - published).days / 365.25
                    if age_years > self.freshness_years:
                        freshness = "outdated"
                except ValueError:
                    pass

        # 4. corroboration across sources
        distinct_sources = {ev.source_id for ev in evidence}
        if len(distinct_sources) >= 2:
            status = ClaimStatus.SUPPORTED.value
            notes = f"Supported by {len(distinct_sources)} independent sources."
        else:
            status = ClaimStatus.PARTIALLY_SUPPORTED.value
            notes = "Only one independent source; treat with caution."

        if freshness == "outdated":
            status = ClaimStatus.OUTDATED.value
            notes = f"Source older than {self.freshness_years} years. " + notes

        self.claims.update(claim.id, support_status=status, freshness=freshness,
                           verification_notes=notes)
        self._log(claim, status, notes)
        return ClaimVerification(
            claim.id, claim.text, status, "none", freshness,
            len(evidence), src_domains, notes=notes,
        )

    # -- full gate -------------------------------------------------------------

    def verify_run(
        self,
        synthesis: str,
        claims: Sequence[Claim],
        *,
        tool_failures: Optional[List[str]] = None,
    ) -> VerificationReport:
        report = VerificationReport(tool_failures=list(tool_failures or []))

        for claim in claims:
            report.claim_verifications.append(self.check_claim(claim))

        # 5. did the synthesis introduce claims that were never registered?
        supported_sentences = _split_sentences(synthesis)
        claim_wordsets = [set(normalize(c.text)) for c in claims]
        for sentence in supported_sentences:
            words = set(normalize(sentence))
            if len(words) < 4:
                continue
            covered = any(len(words & cw) / max(len(words), 1) >= 0.6 for cw in claim_wordsets)
            if not covered:
                report.unsupported_in_synthesis.append(sentence)
                report.gate_log.append(f"synthesis sentence not traceable to a claim: {sentence[:80]}")

        # 6. gate decision
        blocking = [
            cv for cv in report.claim_verifications
            if cv.support_status == ClaimStatus.UNVERIFIED.value
        ]
        if blocking:
            report.gate_log.append(f"{len(blocking)} claim(s) lack evidence -> revise or mark unverified")
        if report.unsupported_in_synthesis:
            report.gate_log.append("synthesis introduced unsupported statements -> rewrite needed")
        if report.tool_failures:
            report.gate_log.append("tool failures occurred -> disclose limitation")

        report.passed = (
            not blocking
            and not report.unsupported_in_synthesis
            and all(cv.support_status not in (ClaimStatus.UNVERIFIED.value,) for cv in report.claim_verifications)
        )
        if self.audit:
            self.audit.log(
                "verification.gate",
                passed=report.passed,
                summary=report.summary(),
            )
        return report

    def _log(self, claim: Claim, status: str, note: str) -> None:
        if self.audit:
            self.audit.log("claim.status", claim_id=claim.id, status=status, note=note[:200])


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text or "")
    return [p.strip() for p in parts if len(p.strip()) > 15]

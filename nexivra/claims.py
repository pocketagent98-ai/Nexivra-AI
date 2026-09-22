"""ClaimRegistry — every important factual claim gets an internal record."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .types import Claim, ClaimStatus, new_id

from .evidence import RegistryError


class ClaimRegistry:
    """Registers claims, links them to evidence/source ids, and records the
    support / conflict / freshness statuses the verification engine sets."""

    def __init__(self) -> None:
        self._by_id: Dict[str, Claim] = {}

    def register(
        self,
        text: str,
        *,
        sources: Optional[List[str]] = None,
        research_task_id: Optional[str] = None,
        support_status: str = ClaimStatus.UNVERIFIED.value,
    ) -> Claim:
        if not text or not text.strip():
            raise RegistryError("claim text must be non-empty")
        claim = Claim(
            id=new_id("clm"),
            text=text.strip(),
            sources=list(sources or []),
            research_task_id=research_task_id,
            support_status=support_status,
        )
        self._by_id[claim.id] = claim
        return claim

    def get(self, claim_id: str) -> Claim:
        try:
            return self._by_id[claim_id]
        except KeyError as exc:
            raise RegistryError(f"unknown claim: {claim_id}") from exc

    def update(
        self,
        claim_id: str,
        *,
        support_status: Optional[str] = None,
        conflict_status: Optional[str] = None,
        freshness: Optional[str] = None,
        verification_notes: Optional[str] = None,
        add_sources: Optional[List[str]] = None,
    ) -> Claim:
        claim = self.get(claim_id)
        if support_status is not None:
            valid = {s.value for s in ClaimStatus}
            if support_status not in valid:
                raise RegistryError(f"invalid status {support_status!r}; valid: {sorted(valid)}")
            claim.support_status = support_status
        if conflict_status is not None:
            claim.conflict_status = conflict_status
        if freshness is not None:
            claim.freshness = freshness
        if verification_notes is not None:
            claim.verification_notes = verification_notes
        if add_sources:
            for s in add_sources:
                if s not in claim.sources:
                    claim.sources.append(s)
        return claim

    def find(self, pred: Callable[[Claim], bool]) -> List[Claim]:
        return [c for c in self._by_id.values() if pred(c)]

    def by_status(self, status: str) -> List[Claim]:
        return self.find(lambda c: c.support_status == status)

    def all(self) -> List[Claim]:
        return list(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

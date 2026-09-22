"""Contradiction detection.

When sources disagree, the disagreement is surfaced — never silently
resolved (build spec section 6). This detector is deliberately rule-based
so it is deterministic and testable offline; an LLM-based explainer can
be layered on top, but the *decision* that a conflict exists must not
depend on a model hallucinating agreement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import Claim, Evidence, Source

_NUM_RE = re.compile(
    r"(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>million|billion|trillion|thousand|%|percent|"
    r"M|B|T|bn|mn|km|kg|miles?|meters?|USD|\$|€|£|₹|years?|GW|MW|TB|GB|MB)?",
    re.IGNORECASE,
)

UNIT_FAMILIES = {
    "million": "count", "mn": "count", "m": "count", "billion": "count", "bn": "count",
    "b": "count", "trillion": "count", "t": "count", "thousand": "count",
    "%": "percent", "percent": "percent",
    "usd": "usd", "$": "usd", "€": "eur", "£": "gbp", "₹": "inr",
    "km": "length", "miles": "length", "meters": "length", "meter": "length",
    "kg": "mass", "gw": "power", "mw": "power", "years": "time", "year": "time",
    "tb": "data", "gb": "data", "mb": "data",
}


def extract_measurements(text: str) -> List[Dict[str, object]]:
    """Pull (value, unit, context) triples out of free text."""
    out: List[Dict[str, object]] = []
    for m in _NUM_RE.finditer(text):
        try:
            value = float(m.group("value"))
        except ValueError:  # pragma: no cover
            continue
        unit = (m.group("unit") or "").strip()
        start = max(0, m.start() - 40)
        out.append({
            "value": value,
            "unit": unit,
            "family": UNIT_FAMILIES.get(unit.lower(), "raw"),
            "context": text[start:m.end() + 40].strip(),
        })
    return out


@dataclass
class ConflictReport:
    has_conflict: bool = False
    kind: str = "none"                    # none | numeric | missing-corroboration
    detail: str = ""
    values: List[Dict[str, object]] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "has_conflict": self.has_conflict,
            "kind": self.kind,
            "detail": self.detail,
            "values": self.values,
            "explanation": self.explanation,
        }


class ContradictionDetector:
    """Compares the measurements carried by a claim's evidence records."""

    def __init__(self, *, tolerance: float = 0.02) -> None:
        # two numbers count as agreeing within 2% relative difference
        self.tolerance = tolerance

    def _source_of(self, source_id: str, sources: List[Source]) -> Optional[Source]:
        return next((s for s in sources if s.id == source_id), None)

    def check(
        self,
        claim: Claim,
        evidence: List[Evidence],
        sources: List[Source],
    ) -> ConflictReport:
        # 1. gather every measurement attached to the claim (from claim or evidence)
        readings: List[Dict[str, object]] = []
        for ev in evidence:
            if ev.id not in claim.sources and ev.source_id not in claim.sources:
                continue
            for meas in ev.measurements or []:
                readings.append({**meas, "evidence_id": ev.id, "source_id": ev.source_id})
        for meas in claim.measurements:
            readings.append({**meas, "evidence_id": None, "source_id": None})

        # 2. group comparable readings by (family, unit-normalised)
        groups: Dict[tuple, List[Dict[str, object]]] = {}
        for r in readings:
            family = str(r.get("family", "raw"))
            unit = str(r.get("unit", "") or "").lower()
            if family in ("raw", "time"):  # raw numbers/dates are too ambiguous to auto-compare
                continue
            key = (family, unit)
            groups.setdefault(key, []).append(r)

        # 3. any value-pair inside a group that disagrees beyond tolerance is a conflict
        for (family, unit), group in groups.items():
            vals = [float(g["value"]) for g in group]
            if len(vals) >= 2:
                lo, hi = min(vals), max(vals)
                if hi != 0 and (hi - lo) / max(abs(hi), abs(lo)) > self.tolerance:
                    per_source = []
                    for g in group:
                        src = self._source_of(str(g.get("source_id") or ""), sources)
                        per_source.append({
                            "value": g["value"],
                            "unit": g.get("unit"),
                            "source": (src.url if src else None),
                            "domain": (src.domain if src else None),
                            "published_at": (src.published_at if src else None),
                            "context": g.get("context"),
                        })
                    explanation = self.explain(claim, per_source)
                    return ConflictReport(
                        has_conflict=True,
                        kind="numeric",
                        detail=f"{family} values disagree: {sorted(set(vals))}",
                        values=per_source,
                        explanation=explanation,
                    )
        return ConflictReport(has_conflict=False)

    @staticmethod
    def explain(claim: Claim, conflicting: List[Dict[str, object]]) -> str:
        """Structured explanation of a conflict: dates, definitions,
        methodology, geography, source authority — in that order."""
        lines = [f"Conflict on claim: {claim.text!r}"]
        dates = sorted({str(c.get("published_at")) for c in conflicting if c.get("published_at")})
        if len(dates) > 1:
            lines.append(
                f"- Sources were published at different times ({', '.join(dates)}); "
                "figures may reflect different reporting periods."
            )
        domains = {str(c.get("domain")) for c in conflicting if c.get("domain")}
        if len(domains) > 1:
            lines.append(
                f"- Sources come from different publishers ({', '.join(sorted(domains))}); "
                "definitions or methodologies may differ."
            )
        lines.append(
            "- The final answer must present both figures and state that evidence is "
            "conflicting; it may not silently pick one."
        )
        return "\n".join(lines)

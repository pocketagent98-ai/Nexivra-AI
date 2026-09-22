"""Offline demo of the Nexivra AI pipeline.

Runs the full ASK -> PLAN -> RESEARCH -> COLLECT EVIDENCE -> CROSS-CHECK
-> VERIFY -> SYNTHESIZE flow with a deterministic in-memory model adapter
and canned sources — no network, no API keys. It deliberately includes a
conflicting source and a stale source so you can see the verification
gate at work.

Usage:
    python examples/demo_offline.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nexivra.adapters import ChatMessage, StaticAdapter
from nexivra.audit import AuditLogger
from nexivra.gateway import ModelProfile, UniversalModelGateway
from nexivra.quotas import ModelBudget, QuotaGovernor
from nexivra.research import ResearchEngine, ResearchMode, SearchHit
from tests.conftest import CannedFetch, CannedSearch

QUESTION = "What was Acme Corp's annual revenue for the last fiscal year?"


def build_engine() -> ResearchEngine:
    audit = AuditLogger()
    quotas = QuotaGovernor(
        {"static/*": ModelBudget(requests=50)},
        audit=audit,
    )
    gateway = UniversalModelGateway(quotas=quotas, audit=audit)
    gateway.register_adapter(StaticAdapter(
        name="static",
        default=f"TASK: Find Acme Corp annual revenue figures from filings and independent analyses.",
    ))
    gateway.add_profile(ModelProfile(provider="static", model="static-1"))

    hits = [
        SearchHit("https://filings.example/acme-2025", "Acme Corp 10-K filing", "", "2025-11-30", tier=4),
        SearchHit("https://analyst.example/acme-report", "Independent analyst report", "", "2025-12-15"),
        SearchHit("https://press.example/acme-old", "Older press release", "", "2019-01-10"),
    ]
    bodies = {
        "https://filings.example/acme-2025":
            "Acme Corp reported annual revenue of 50 million USD for fiscal 2025, according to its filing.",
        "https://analyst.example/acme-report":
            "Our independent analysis estimates Acme Corp revenue at 47 million USD for the same fiscal period.",
        "https://press.example/acme-old":
            "Acme Corp announced revenue of 20 million USD in the 2018 annual report.",
    }
    return ResearchEngine(
        gateway=gateway,
        search_tool=CannedSearch({"revenue": hits}),
        fetch_tool=CannedFetch(bodies),
        audit=audit,
        mode=ResearchMode.VERIFIED_DEEP,
    )


def main() -> None:
    engine = build_engine()
    report = asyncio.run(engine.run(QUESTION))

    print("=" * 78)
    print("Nexivra AI — offline Verified Deep demo")
    print("=" * 78)
    print(f"\nQuestion: {report.question}\n")
    print("PLAN:")
    for task in report.plan:
        print(f"  - [{task['role']}] {task['description']}")
    print("\nSOURCES:")
    for s in report.sources:
        print(f"  - {s['domain']} ({s.get('published_at') or 'no date'}) — {s['title']}")
    print("\nCLAIMS:")
    for c in report.claims:
        print(f"  [{c['support_status']:^22}] {c['text']}")
        if c.get("conflict"):
            print(f"        conflict: {c['conflict']['detail']}")
    print(f"\nVERIFICATION GATE: {'PASSED' if report.verification['passed'] else 'NOT PASSED'}")
    print(f"  {report.verification['summary']}")
    if report.tool_failures:
        print("  tool failures disclosed:")
        for f in report.tool_failures:
            print(f"    ! {f}")
    print("\nSYNTHESIS:")
    print(report.synthesis)
    print("\nMODEL USAGE:", json.dumps(report.usage))
    print("\nFull JSON report: report = engine.run(...)  ->  report.to_dict()")


if __name__ == "__main__":
    main()

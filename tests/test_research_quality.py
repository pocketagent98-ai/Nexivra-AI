"""Research-quality tests (build spec section 19): conflicting sources,
outdated sources, unsupported claims, tool failures, injection."""

import asyncio

from nexivra.research import ResearchEngine, ResearchMode, RunLimits, SearchHit

from conftest import CannedFetch, CannedSearch, build_gateway


def _run_with(hits, bodies, question="What was the revenue?", script=None):
    gw, audit, _ = build_gateway(script=script, default="TASK: What was the revenue?")
    engine = ResearchEngine(
        gateway=gw,
        search_tool=CannedSearch({"revenue": hits}),
        fetch_tool=CannedFetch(bodies),
        audit=audit,
        mode=ResearchMode.VERIFIED_DEEP,
    )
    return asyncio.run(engine.run(question)), engine


def test_conflicting_sources_are_disclosed():
    hits = [
        SearchHit("https://a.example/r", "A", "", "2026-01-01"),
        SearchHit("https://b.example/r", "B", "", "2026-02-01"),
    ]
    bodies = {
        "https://a.example/r": "The company reported revenue of 50 million USD last year.",
        "https://b.example/r": "Our analysis puts revenue at 38 million USD for the same period.",
    }
    report, engine = _run_with(hits, bodies)
    assert any(c["support_status"] == "conflicting" for c in report.claims)
    assert "CONFLICTING EVIDENCE" in report.synthesis
    conflict_claims = [c for c in report.claims if c["support_status"] == "conflicting"]
    assert conflict_claims and conflict_claims[0]["conflict"]["kind"] == "numeric"


def test_outdated_sources_flagged():
    hits = [SearchHit("https://old.example/r", "Old", "", "2014-01-01")]
    bodies = {
        "https://old.example/r": "Revenue was 50 million USD according to the 2014 annual report.",
    }
    report, _ = _run_with(hits, bodies)
    assert any(c["support_status"] == "outdated" for c in report.claims)


def test_single_source_claim_not_asserted_as_independently_verified():
    hits = [SearchHit("https://only.example/r", "Only", "", "2026-01-01")]
    bodies = {"https://only.example/r": "Revenue was 50 million USD per the sole available filing."}
    report, _ = _run_with(hits, bodies)
    assert all(c["support_status"] != "supported" for c in report.claims)
    assert any(c["support_status"] == "partially_supported" for c in report.claims)


def test_no_evidence_yields_honest_empty_answer():
    gw, audit, _ = build_gateway(default="TASK: x")
    engine = ResearchEngine(
        gateway=gw,
        search_tool=CannedSearch(default=[]),
        fetch_tool=CannedFetch({}),
        audit=audit,
        mode=ResearchMode.VERIFIED_DEEP,
    )
    report = asyncio.run(engine.run("What is the airspeed velocity of an unladen swallow?"))
    assert "No verifiable evidence" in report.synthesis
    assert report.claims == []


def test_tool_failure_disclosed_in_final_report():
    hits = [SearchHit("https://a.example/r", "A", "", "2026-01-01")]
    report, _ = _run_with(hits, {})  # fetch will 404
    assert report.tool_failures
    assert report.verification["tool_failures"] == report.tool_failures

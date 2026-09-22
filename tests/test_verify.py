from veriforge.conflicts import extract_measurements
from veriforge.types import ClaimStatus

from conftest import build_verifier


def test_claim_without_evidence_stays_unverified():
    sources, evidence, claims, verifier, _ = build_verifier()
    c = claims.register("Something unverified.")
    cv = verifier.check_claim(c)
    assert cv.support_status == ClaimStatus.UNVERIFIED.value
    assert cv.evidence_count == 0


def test_two_sources_make_supported():
    sources, evidence, claims, verifier, _ = build_verifier()
    s1 = sources.add("https://a.example/1", "A", published_at="2026-01-01")
    s2 = sources.add("https://b.example/2", "B", published_at="2026-02-01")
    e1 = evidence.add(s1.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    e2 = evidence.add(s2.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    c = claims.register("Revenue was 50 million USD.", sources=[e1.id, e2.id])
    cv = verifier.check_claim(c)
    assert cv.support_status == ClaimStatus.SUPPORTED.value
    assert cv.freshness == "recent"
    assert set(cv.source_domains) == {"a.example", "b.example"}


def test_single_source_is_only_partial():
    sources, evidence, claims, verifier, _ = build_verifier()
    s1 = sources.add("https://a.example/1", "A", published_at="2026-01-01")
    e1 = evidence.add(s1.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    c = claims.register("Revenue was 50 million USD.", sources=[e1.id])
    cv = verifier.check_claim(c)
    assert cv.support_status == ClaimStatus.PARTIALLY_SUPPORTED.value
    assert "caution" in cv.notes.lower()


def test_stale_source_marks_outdated():
    sources, evidence, claims, verifier, _ = build_verifier()
    s1 = sources.add("https://old.example/1", "Old", published_at="2015-01-01")
    s2 = sources.add("https://old2.example/2", "Old2", published_at="2016-01-01")
    e1 = evidence.add(s1.id, "User base was 5 million.", measurements=extract_measurements("User base was 5 million."))
    e2 = evidence.add(s2.id, "User base was 5 million.", measurements=extract_measurements("User base was 5 million."))
    c = claims.register("User base was 5 million.", sources=[e1.id, e2.id])
    cv = verifier.check_claim(c)
    assert cv.support_status == ClaimStatus.OUTDATED.value
    assert cv.freshness == "outdated"


def test_conflicting_sources_flagged_not_resolved():
    sources, evidence, claims, verifier, _ = build_verifier()
    s1 = sources.add("https://a.example/1", "A", published_at="2026-01-01")
    s2 = sources.add("https://b.example/2", "B", published_at="2026-03-01")
    e1 = evidence.add(s1.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    e2 = evidence.add(s2.id, "Revenue was 47 million USD.", measurements=extract_measurements("Revenue was 47 million USD."))
    c = claims.register("Revenue was 50 million USD.", sources=[e1.id, e2.id])
    cv = verifier.check_claim(c)
    assert cv.support_status == ClaimStatus.CONFLICTING.value
    assert cv.conflict is not None and cv.conflict.has_conflict


def test_gate_detects_unsupported_synthesis_claims():
    sources, evidence, claims, verifier, _ = build_verifier()
    s1 = sources.add("https://a.example/1", "A", published_at="2026-01-01")
    s2 = sources.add("https://b.example/2", "B", published_at="2026-01-02")
    e1 = evidence.add(s1.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    e2 = evidence.add(s2.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    c = claims.register("Revenue was 50 million USD.", sources=[e1.id, e2.id])

    synthesis = (
        "Revenue was 50 million USD in the last fiscal year. "
        "The company also plans to open a new headquarters on Mars by 2030."
    )
    report = verifier.verify_run(synthesis, [c])
    assert any("Mars" in s for s in report.unsupported_in_synthesis)
    assert not report.passed


def test_gate_passes_on_clean_run():
    sources, evidence, claims, verifier, _ = build_verifier()
    s1 = sources.add("https://a.example/1", "A", published_at="2026-01-01")
    s2 = sources.add("https://b.example/2", "B", published_at="2026-01-02")
    e1 = evidence.add(s1.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    e2 = evidence.add(s2.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    c = claims.register("Revenue was 50 million USD.", sources=[e1.id, e2.id])
    report = verifier.verify_run("Revenue was 50 million USD.", [c])
    assert report.passed
    assert report.status_counts == {"supported": 1}


def test_tool_failures_disclosed_in_gate():
    sources, evidence, claims, verifier, _ = build_verifier()
    c = claims.register("Unverifiable claim.")
    report = verifier.verify_run("", [c], tool_failures=["search backend down"])
    assert report.tool_failures
    assert any("tool failures" in g for g in report.gate_log)

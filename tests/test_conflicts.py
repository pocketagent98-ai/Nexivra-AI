from veriforge.conflicts import ContradictionDetector, extract_measurements
from veriforge.types import Claim, Evidence

from conftest import build_verifier


def test_extract_measurements_finds_values_and_units():
    ms = extract_measurements("The company earned 50 million USD in 2024, up 12% year over year.")
    vals = {(m["value"], (m["unit"] or "").lower()) for m in ms}
    assert (50.0, "million") in vals
    assert (12.0, "%") in vals


def test_detector_flags_numeric_disagreement():
    sources, evidence, claims, _, _ = build_verifier()
    s1 = sources.add("https://a.example/r", "Report A", published_at="2026-01-01")
    s2 = sources.add("https://b.example/r", "Report B", published_at="2026-02-01")
    e1 = evidence.add(s1.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    e2 = evidence.add(s2.id, "Revenue was 47 million USD.", measurements=extract_measurements("Revenue was 47 million USD."))
    claim = claims.register("Company revenue was about 50 million USD.", sources=[e1.id, e2.id])

    report = ContradictionDetector().check(claim, [e1, e2], sources.all())
    assert report.has_conflict
    assert report.kind == "numeric"
    assert len(report.values) == 2
    assert "may reflect different reporting periods" in report.explanation or "different publishers" in report.explanation


def test_detector_tolerates_small_rounding_differences():
    sources, evidence, claims, _, _ = build_verifier()
    s1 = sources.add("https://a.example/r", "A")
    s2 = sources.add("https://b.example/r", "B")
    e1 = evidence.add(s1.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    e2 = evidence.add(s2.id, "Revenue was 50.5 million USD.", measurements=extract_measurements("Revenue was 50.5 million USD."))
    claim = claims.register("Revenue was about 50 million USD.", sources=[e1.id, e2.id])
    assert not ContradictionDetector().check(claim, [e1, e2], sources.all()).has_conflict


def test_detector_no_conflict_with_single_reading():
    sources, evidence, claims, _, _ = build_verifier()
    s1 = sources.add("https://a.example/r", "A")
    e1 = evidence.add(s1.id, "Revenue was 50 million USD.", measurements=extract_measurements("Revenue was 50 million USD."))
    claim = claims.register("Revenue was 50 million USD.", sources=[e1.id])
    assert not ContradictionDetector().check(claim, [e1], sources.all()).has_conflict

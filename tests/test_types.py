from nexivra.types import ClaimStatus, SourceTier, content_hash


def test_all_claim_statuses_present():
    values = {s.value for s in ClaimStatus}
    assert values == {
        "supported", "partially_supported", "conflicting",
        "unverified", "outdated", "opinion", "inference",
    }


def test_source_tier_order():
    assert SourceTier.OFFICIAL_PRIMARY < SourceTier.COMMUNITY
    assert SourceTier.label(SourceTier.ACADEMIC) == "academic"


def test_content_hash_stable():
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("world")


def test_claim_is_ok_semantics():
    import nexivra.types as t
    ok = t.Claim(id="c1", text="x", support_status=ClaimStatus.SUPPORTED.value)
    bad = t.Claim(id="c2", text="x", support_status=ClaimStatus.UNVERIFIED.value)
    assert ok.is_ok and not bad.is_ok

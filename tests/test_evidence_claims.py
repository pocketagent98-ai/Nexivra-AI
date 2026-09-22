import pytest

from nexivra.claims import ClaimRegistry
from nexivra.evidence import EvidenceStore, RegistryError, SourceRegistry
from nexivra.types import ClaimStatus


def test_source_dedupe_by_url():
    reg = SourceRegistry()
    a = reg.add("https://a.example/x", "A", body="hello")
    b = reg.add("https://a.example/x", "A again")
    assert a.id == b.id
    assert len(reg) == 1


def test_source_dedupe_by_content_hash():
    reg = SourceRegistry()
    reg.add("https://a.example/1", "A", body="same body text")
    reg.add("https://b.example/2", "B", body="same body text")
    assert reg.dedupe_body("same body text")
    assert not reg.dedupe_body("different")


def test_source_requires_url_and_title():
    with pytest.raises(RegistryError):
        SourceRegistry().add("", "title")
    with pytest.raises(RegistryError):
        SourceRegistry().add("https://a.example", "")


def test_evidence_add_and_lookup():
    reg = SourceRegistry()
    src = reg.add("https://a.example", "A")
    store = EvidenceStore()
    ev = store.add(src.id, "Revenue was 5 million USD.", quote="5 million USD")
    assert store.get(ev.id).source_id == src.id
    assert len(store.by_source(src.id)) == 1
    assert store.for_claim(Claim_stub(ev.id)) == [ev]


def Claim_stub(evidence_id):
    from nexivra.types import Claim
    return Claim(id="c", text="t", sources=[evidence_id])


def test_evidence_rejects_empty_excerpt():
    with pytest.raises(RegistryError):
        EvidenceStore().add("src", "   ")


def test_claim_registration_and_update():
    reg = ClaimRegistry()
    c = reg.register("The sky is blue.")
    assert c.support_status == ClaimStatus.UNVERIFIED.value
    reg.update(c.id, support_status=ClaimStatus.SUPPORTED.value, freshness="recent")
    assert reg.get(c.id).support_status == "supported"
    assert reg.by_status("supported") == [reg.get(c.id)]


def test_claim_invalid_status_rejected():
    reg = ClaimRegistry()
    c = reg.register("x")
    with pytest.raises(RegistryError):
        reg.update(c.id, support_status="totally-true")


def test_claim_empty_text_rejected():
    with pytest.raises(RegistryError):
        ClaimRegistry().register("  ")

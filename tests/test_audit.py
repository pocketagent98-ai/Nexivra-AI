from nexivra.audit import AuditLogger, mask


def test_mask_credential_named_fields():
    rec = {"api_key": "nvapi-secret", "model": "m1", "nested": {"token": "x", "ok": 1}}
    out = mask(rec)
    assert out["api_key"] == "***masked***"
    assert out["model"] == "m1"
    assert out["nested"]["token"] == "***masked***"
    assert out["nested"]["ok"] == 1


def test_mask_known_secret_prefixes():
    assert mask("nvapi-abcdef123456") == "***masked***"
    assert mask("sk-12345") == "***masked***"
    assert mask("Bearer abc") == "***masked***"
    assert mask("hello world") == "hello world"


def test_jsonl_trail_written_and_queryable():
    logger = AuditLogger()
    logger.log("model.call", task="plan", provider="static", model="static-1")
    logger.log("model.error", task="plan", provider="static", model="static-1", api_key="nvapi-x")
    assert len(logger.events_of("model.call")) == 1
    err = logger.events_of("model.error")[0]
    assert err["api_key"] == "***masked***"
    assert logger.search(task="plan", event="model.call")

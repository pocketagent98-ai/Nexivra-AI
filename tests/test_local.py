"""Tests for the API-aware cloud/local loading gate (Nexivra update
sections 5–6): cloud routing, local routing, switching, model unload,
key failure, 429, timeout, quota exhaustion, lazy loading."""

import urllib.error

from nexivra.audit import AuditLogger
from nexivra.local import (
    APIAwareRouter,
    DeviceProfile,
    FailureKind,
    LocalModelUnavailable,
    QWEN3_06B,
    SMOLLM2_135M,
    StubLocalRuntime,
    classify_failure,
)
from nexivra.quotas import BudgetExhausted


class FlippableProbe:
    """Cloud health probe whose result can be flipped mid-test."""

    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    def __call__(self) -> bool:
        return self.healthy


# -- failure classification -------------------------------------------------

def test_classify_missing_key():
    assert classify_failure(has_key=False) == FailureKind.MISSING_KEY


def test_classify_invalid_key():
    assert classify_failure(status=401) == FailureKind.INVALID_KEY
    assert classify_failure(status=403) == FailureKind.INVALID_KEY


def test_classify_rate_limited():
    assert classify_failure(status=429) == FailureKind.RATE_LIMITED


def test_classify_server_error_and_outage():
    assert classify_failure(status=500) == FailureKind.SERVER_ERROR
    assert classify_failure(status=503) == FailureKind.SERVER_ERROR


def test_classify_timeout():
    assert classify_failure(status=408) == FailureKind.TIMEOUT
    assert classify_failure(exc=TimeoutError()) == FailureKind.TIMEOUT


def test_classify_quota_exhausted():
    assert classify_failure(exc=BudgetExhausted("over budget")) == FailureKind.QUOTA_EXHAUSTED


def test_classify_network_offline():
    assert classify_failure(exc=urllib.error.URLError("no route")) == FailureKind.NETWORK_OFFLINE
    assert classify_failure(exc=ConnectionError()) == FailureKind.NETWORK_OFFLINE


def test_classify_http_error_exception_carries_status():
    err = urllib.error.HTTPError(None, 429, "Too Many Requests", None, None)  # type: ignore[arg-type]
    assert classify_failure(exc=err) == FailureKind.RATE_LIMITED


# -- device profiles -----------------------------------------------------------

def test_device_profile_context_windows():
    assert DeviceProfile.LITE.context_tokens == 2048
    assert DeviceProfile.BALANCED.context_tokens == 4096
    assert DeviceProfile.LITE.max_generation_tokens <= DeviceProfile.BALANCED.max_generation_tokens


# -- router: cloud-first loading gate -------------------------------------------

def _router(cloud_healthy: bool, runtime=None, **kw):
    runtime = runtime or StubLocalRuntime()
    router = APIAwareRouter(
        cloud_probe=lambda: cloud_healthy,
        local_runtime=runtime,
        audit=None,
        **kw,
    )
    return router, runtime


def test_cloud_healthy_routes_cloud_and_never_loads_local():
    router, runtime = _router(True)
    for _ in range(5):
        assert router.route() == "cloud"
    assert runtime.load_calls == []  # local model MUST NOT be loaded


def test_cloud_down_routes_local_and_lazy_loads_once():
    router, runtime = _router(False)
    assert router.route() == "local"
    assert router.route() == "local"
    assert len(runtime.load_calls) == 1  # lazy + loaded exactly once
    assert runtime.load_calls[0]["spec"] == "Qwen3-0.6B"
    assert runtime.load_calls[0]["context_tokens"] == 4096


def test_cloud_recovery_unloads_local_when_safe():
    runtime = StubLocalRuntime()
    probe = FlippableProbe(False)
    router = APIAwareRouter(cloud_probe=probe, local_runtime=runtime)
    assert router.route() == "local"
    assert runtime.is_loaded()

    probe.healthy = True
    assert router.probe_cloud() is True
    assert router.route() == "cloud"
    assert not runtime.is_loaded()          # unloaded when safe
    assert runtime.unload_calls == 1


def test_unload_deferred_while_busy():
    runtime = StubLocalRuntime()
    probe = FlippableProbe(False)
    router = APIAwareRouter(cloud_probe=probe, local_runtime=runtime)
    assert router.route() == "local"
    assert runtime.is_loaded()

    runtime.busy = True                     # mid-generation
    probe.healthy = True
    assert router.probe_cloud() is True     # cloud recovered
    assert runtime.is_loaded()              # unload deferred: busy

    runtime.busy = False
    assert router.probe_cloud() is True
    assert not runtime.is_loaded()           # now unloaded when safe
    assert runtime.unload_calls == 1


def test_report_cloud_failure_switches_next_route_to_local():
    router, runtime = _router(True)
    assert router.route() == "cloud"
    router.report_cloud_failure(FailureKind.RATE_LIMITED)
    assert router.route() == "local"
    assert runtime.is_loaded()


def test_generate_local_requires_load_and_cloud_still_down():
    router, runtime = _router(False)
    try:
        router.generate_local("hi")
        assert False, "should have raised"
    except LocalModelUnavailable:
        pass
    assert router.route() == "local"
    assert router.generate_local("hi") == "[local model reply]"


def test_generate_local_refuses_when_cloud_recovers():
    runtime = StubLocalRuntime()
    probe = FlippableProbe(False)
    router = APIAwareRouter(cloud_probe=probe, local_runtime=runtime)
    assert router.route() == "local"
    assert runtime.is_loaded()

    probe.healthy = True                     # cloud comes back mid-flight
    try:
        router.generate_local("hi")
        assert False, "cloud recovered -> local generation must be refused"
    except LocalModelUnavailable:
        pass


def test_ultra_lite_only_when_explicitly_allowed():
    router, runtime = _router(False, allow_ultra_lite=False, ultra_lite_model=SMOLLM2_135M)
    assert router.route() == "local"
    assert runtime.load_calls[0]["spec"] == "Qwen3-0.6B"

    router2, runtime2 = _router(False, allow_ultra_lite=True, ultra_lite_model=SMOLLM2_135M)
    assert router2.route() == "local"
    assert runtime2.load_calls[0]["spec"] == "SmolLM2-135M-Instruct"


def test_probe_interval_prevents_hammering():
    runtime = StubLocalRuntime()
    calls = {"n": 0}

    def probe():
        calls["n"] += 1
        return False

    router = APIAwareRouter(cloud_probe=probe, local_runtime=runtime, probe_interval_seconds=60.0)
    router.report_cloud_failure(FailureKind.NETWORK_OFFLINE)
    for _ in range(5):
        router.route()
    # probe happens at most once inside the interval, never per route()
    assert calls["n"] <= 1


def test_audit_events_recorded():
    audit = AuditLogger()
    runtime = StubLocalRuntime()
    router = APIAwareRouter(cloud_probe=lambda: False, local_runtime=runtime, audit=audit)
    router.route()
    events = [e["event"] for e in audit.events]
    assert "local.loaded" in events
    assert "route.local" in events

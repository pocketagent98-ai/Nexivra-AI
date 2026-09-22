"""Local AI runtime — cloud-first, API-aware loading (Nexivra update,
spec sections 3–6).

Model path:

    Cloud: DeerFlow -> UniversalModelGateway -> OmniRoute -> authorized provider
    Local: DeerFlow -> UniversalModelGateway -> llama.cpp -> Qwen3-0.6B GGUF

Mandatory loading gate:

    START
      -> is a healthy authorized cloud API available?
         YES -> use cloud; the local model MUST NOT be loaded
         NO  -> lazily load local Qwen3-0.6B
      -> when the cloud becomes healthy again: resume cloud and
         unload the local model when safe.

Runtime rules:
- llama.cpp native runtime + GGUF on device; do NOT require Python,
  PyTorch or Transformers on mobile.
- Local model is lazy-loaded and unloaded when idle.
- Device profiles (Lite / Balanced / Auto) size the context window
  (2048–4096 tokens on low-resource devices) and generation length.
- Never silently switch to a paid API. If neither an authorized free
  cloud API nor a local model is usable, the request fails loudly.

Model honesty: Qwen3-0.6B, SmolLM2 and llama.cpp are third-party
technologies under their own licenses. They are "the local model inside
Nexivra AI", never "a proprietary Nexivra model".
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol

from .audit import AuditLogger
from .quotas import BudgetExhausted

import urllib.error


class FailureKind(str, enum.Enum):
    """Why the cloud API is not usable right now."""

    NONE = "none"
    MISSING_KEY = "missing_key"
    INVALID_KEY = "invalid_key"        # 401 / 403
    RATE_LIMITED = "rate_limited"      # 429
    SERVER_ERROR = "server_error"     # 5xx
    TIMEOUT = "timeout"
    QUOTA_EXHAUSTED = "quota_exhausted"
    PROVIDER_OUTAGE = "provider_outage"
    NETWORK_OFFLINE = "network_offline"
    UNKNOWN = "unknown"


def classify_failure(*, status: Optional[int] = None, exc: Optional[BaseException] = None,
                     has_key: Optional[bool] = None) -> FailureKind:
    """Map an error condition to a FailureKind. Order matters."""
    if has_key is False:
        return FailureKind.MISSING_KEY
    if exc is not None:
        if isinstance(exc, BudgetExhausted):
            return FailureKind.QUOTA_EXHAUSTED
        if isinstance(exc, TimeoutError):
            return FailureKind.TIMEOUT
        if isinstance(exc, urllib.error.HTTPError):
            status = status or exc.code
        elif isinstance(exc, (urllib.error.URLError, ConnectionError, OSError)):
            return FailureKind.NETWORK_OFFLINE
    if status is None:
        return FailureKind.UNKNOWN
    if status in (401, 403):
        return FailureKind.INVALID_KEY
    if status == 429:
        return FailureKind.RATE_LIMITED
    if 500 <= status < 600:
        return FailureKind.SERVER_ERROR
    if status == 408:
        return FailureKind.TIMEOUT
    return FailureKind.UNKNOWN


class DeviceProfile(str, enum.Enum):
    """Low-end device policy. Context starts around 2048–4096 tokens on
    low-resource devices; RAM thresholds are NOT hardcoded — they must be
    derived from real target-device benchmarks."""

    LITE = "lite"
    BALANCED = "balanced"
    AUTO = "auto"

    @property
    def context_tokens(self) -> int:
        return {DeviceProfile.LITE: 2048, DeviceProfile.BALANCED: 4096, DeviceProfile.AUTO: 4096}[self]

    @property
    def max_generation_tokens(self) -> int:
        # conservative generation length on constrained devices
        return {DeviceProfile.LITE: 256, DeviceProfile.BALANCED: 1024, DeviceProfile.AUTO: 1024}[self]


@dataclass
class LocalModelSpec:
    name: str
    gguf_path: str
    quant: str = "Q4_0"
    approximate_size_mb: int = 429          # Qwen3-0.6B Q4_0 listing, verify per build
    license: str = "Apache-2.0"
    role: str = "primary"                    # primary | ultra_lite


QWEN3_06B = LocalModelSpec(
    name="Qwen3-0.6B",
    gguf_path="models/qwen3-0.6b-q4_0.gguf",
    quant="Q4_0",
    approximate_size_mb=429,
    role="primary",
)

# Optional emergency ultra-lite. English-centric per its model card — never
# the default worldwide model. RWKV-4 169M is deliberately NOT offered.
SMOLLM2_135M = LocalModelSpec(
    name="SmolLM2-135M-Instruct",
    gguf_path="models/smollm2-135m-instruct-q4_0.gguf",
    approximate_size_mb=110,
    role="ultra_lite",
)


class LocalRuntime(Protocol):
    """Abstract llama.cpp-backed runtime. A native app binds this to the
    llama.cpp Android/native API; tests bind a stub."""

    def load(self, spec: LocalModelSpec, *, context_tokens: int) -> None: ...

    def unload(self) -> None: ...

    def is_loaded(self) -> bool: ...

    def generate(self, prompt: str, *, max_tokens: int) -> str: ...


class StubLocalRuntime:
    """Deterministic in-memory runtime for tests and the offline demo."""

    def __init__(self, reply: str = "[local model reply]") -> None:
        self.reply = reply
        self.load_calls: List[Dict[str, object]] = []
        self.unload_calls = 0
        self._loaded: Optional[LocalModelSpec] = None
        self.busy = False  # set by tests to simulate mid-generation

    def load(self, spec: LocalModelSpec, *, context_tokens: int) -> None:
        self.load_calls.append({"spec": spec.name, "context_tokens": context_tokens})
        self._loaded = spec

    def unload(self) -> None:
        self.unload_calls += 1
        self._loaded = None

    def is_loaded(self) -> bool:
        return self._loaded is not None

    def generate(self, prompt: str, *, max_tokens: int) -> str:
        if not self.is_loaded():
            raise RuntimeError("local model not loaded")
        return self.reply


class LocalModelUnavailable(RuntimeError):
    """Neither an authorized cloud API nor a usable local model exists.
    Raised instead of ever silently switching to a paid API."""


@dataclass
class _CloudState:
    healthy: bool = True
    last_failure: FailureKind = FailureKind.NONE
    failures: int = 0
    checked_at: float = 0.0


class APIAwareRouter:
    """The mandatory cloud-first loading gate.

    ``cloud_probe`` is a callable returning True when a healthy,
    authorized cloud API is available (a cheap models() call). The local
    runtime is only ever loaded lazily, when the cloud is unusable, and is
    unloaded as soon as the cloud is healthy again and the runtime is not
    mid-generation ("when safe").
    """

    def __init__(
        self,
        *,
        cloud_probe: Callable[[], bool],
        local_runtime: LocalRuntime,
        primary_model: LocalModelSpec = QWEN3_06B,
        ultra_lite_model: Optional[LocalModelSpec] = None,
        profile: DeviceProfile = DeviceProfile.AUTO,
        allow_ultra_lite: bool = False,
        audit: Optional[AuditLogger] = None,
        probe_interval_seconds: float = 30.0,
    ) -> None:
        self.cloud_probe = cloud_probe
        self.runtime = local_runtime
        self.primary_model = primary_model
        self.ultra_lite_model = ultra_lite_model
        self.profile = profile
        self.allow_ultra_lite = allow_ultra_lite
        self.audit = audit or AuditLogger()
        self._cloud = _CloudState()
        self._probe_interval = probe_interval_seconds
        self._last_route: str = "cloud"

    # -- cloud health -------------------------------------------------------

    def _cloud_available(self) -> bool:
        if self._cloud.checked_at == 0.0 or (time.monotonic() - self._cloud.checked_at) >= self._probe_interval:
            self.probe_cloud()
        return self._cloud.healthy

    def probe_cloud(self) -> bool:
        self._cloud.checked_at = time.monotonic()
        try:
            healthy = bool(self.cloud_probe())
        except Exception:
            healthy = False
        if healthy:
            recovered = not self._cloud.healthy
            self._cloud.healthy = True
            self._cloud.failures = 0
            if recovered:
                self._log("cloud.recovered")
            # idempotent no-op when the local model is not loaded or busy;
            # also covers the case where it became safe after recovery
            self._unload_local_if_safe()
        else:
            self._cloud.healthy = False
        return healthy

    def report_cloud_failure(self, kind: FailureKind) -> None:
        """Called when a cloud request fails. Marks the cloud unusable so
        the next request goes to the local model."""
        self._cloud.healthy = False
        self._cloud.last_failure = kind
        self._cloud.failures += 1
        self._log("cloud.failed", kind=kind.value, failures=self._cloud.failures)

    # -- routing ------------------------------------------------------------

    @property
    def active_model_spec(self) -> Optional[LocalModelSpec]:
        return self._active_spec

    def route(self) -> str:
        """Return 'cloud' or 'local'. Local model is loaded lazily here and
        ONLY here; it must never be loaded while the cloud is healthy."""
        if self._cloud_available():
            self._last_route = "cloud"
            self._log("route.cloud")
            return "cloud"

        spec = self._select_local_spec()
        if not self.runtime.is_loaded():
            self.runtime.load(spec, context_tokens=self.profile.context_tokens)
            self._log("local.loaded", model=spec.name,
                      context_tokens=self.profile.context_tokens)
        self._last_route = "local"
        self._log("route.local", model=spec.name)
        return "local"

    def generate_local(self, prompt: str) -> str:
        """Generate with the local model (only valid after route()=='local').

        Follows the spec recovery flow: local -> cloud health probe ->
        cloud healthy -> resume cloud (and unload local). So we probe
        before every local generation."""
        if not self.runtime.is_loaded():
            raise LocalModelUnavailable("local model not loaded; call route() first")
        if self.probe_cloud():
            # cloud came back mid-flight: do not keep using local
            raise LocalModelUnavailable("cloud recovered; route() again")
        return self.runtime.generate(
            prompt, max_tokens=self.profile.max_generation_tokens
        )

    def _select_local_spec(self) -> LocalModelSpec:
        if self.allow_ultra_lite and self.ultra_lite_model is not None:
            return self.ultra_lite_model
        return self.primary_model

    def _unload_local_if_safe(self) -> None:
        if not self.runtime.is_loaded():
            return
        busy = getattr(self.runtime, "busy", False)
        if busy:
            self._log("local.unload_deferred")
            return
        self.runtime.unload()
        self._log("local.unloaded")

    def _log(self, event: str, **fields: object) -> None:
        self.audit.log(event, **fields)

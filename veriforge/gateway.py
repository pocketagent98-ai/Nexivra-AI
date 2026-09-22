"""UniversalModelGateway — the single chokepoint for model access.

Application code NEVER talks to a provider directly (build spec
section 8). Everything goes:

    Application -> UniversalModelGateway -> adapter -> provider

Preferred deployment path (section 2):

    DeerFlow (harness) -> UniversalModelGateway -> OmniRoute adapter ->
    provider adapter. FreeLLMAPI stays an optional adapter, never a second
    router stacked under OmniRoute.

The gateway enforces, per request:
- quota governance (reserve before, record after, never silently pay);
- a configurable rate limit per provider (NO permanent hardcoded RPM —
  the value is a profile setting that must be verified against the live
  provider);
- fallback down the model chain on retryable errors;
- audit logging with secrets masked out.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .adapters import AdapterError, ChatMessage, ChatResult, ProviderAdapter
from .audit import AuditLogger
from .quotas import BudgetExhausted, QuotaGovernor
from .types import _now_iso

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class RouterError(RuntimeError):
    """Every model in the chain failed."""


@dataclass
class ModelProfile:
    provider: str
    model: str
    capabilities: List[str] = field(default_factory=lambda: ["chat"])
    rpm_limit: Optional[int] = None      # configurable; verify against the live provider
    context_window: Optional[int] = None
    paid: bool = False
    priority: int = 100                  # lower = tried earlier


class _RateBucket:
    """Simple per-provider pacing. rpm_limit is a *setting*, not a promise."""

    def __init__(self, rpm: Optional[int]) -> None:
        self.rpm = rpm
        self._timestamps: List[float] = []

    def wait_time(self) -> float:
        if not self.rpm:
            return 0.0
        now = time.monotonic()
        self._timestamps = [t for t in self._timestamps if now - t < 60.0]
        if len(self._timestamps) < self.rpm:
            return 0.0
        return max(0.0, 60.0 - (now - self._timestamps[0]))

    def record(self) -> None:
        self._timestamps.append(time.monotonic())


@dataclass
class _Route:
    profile: ModelProfile
    adapter: ProviderAdapter
    api_key: str


class UniversalModelGateway:
    def __init__(
        self,
        *,
        vault: Any = None,
        quotas: Optional[QuotaGovernor] = None,
        audit: Optional[AuditLogger] = None,
    ) -> None:
        self._adapters: Dict[str, ProviderAdapter] = {}
        self._profiles: List[ModelProfile] = []
        self._vault = vault
        self.quotas = quotas or QuotaGovernor()
        self.audit = audit or AuditLogger()
        self._buckets: Dict[str, _RateBucket] = {}

    # -- registration --------------------------------------------------

    def register_adapter(self, adapter: ProviderAdapter) -> None:
        self._adapters[adapter.name] = adapter
        self._buckets.setdefault(adapter.name, _RateBucket(None))

    def add_profile(self, profile: ModelProfile, *, rpm_limit: Optional[int] = None) -> None:
        if profile.provider not in self._adapters:
            raise RouterError(f"no adapter registered for provider {profile.provider!r}")
        profile.rpm_limit = rpm_limit if rpm_limit is not None else profile.rpm_limit
        self._buckets[profile.provider] = _RateBucket(profile.rpm_limit)
        self._profiles.append(profile)
        self._profiles.sort(key=lambda p: p.priority)

    def profiles(self) -> List[ModelProfile]:
        return list(self._profiles)

    def _routes(self, capability: str = "chat") -> List[_Route]:
        routes = []
        for prof in self._profiles:
            if capability not in prof.capabilities:
                continue
            adapter = self._adapters[prof.provider]
            if self._vault is not None and self._vault.exists(prof.provider):
                api_key = self._vault.get(prof.provider)
            else:
                api_key = ""
            routes.append(_Route(profile=prof, adapter=adapter, api_key=api_key))
        return routes

    # -- public API --------------------------------------------------------

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        capability: str = "chat",
        task: str = "chat",
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> ChatResult:
        routes = self._routes(capability)
        if not routes:
            raise RouterError("no model route registered")
        errors: List[str] = []
        quota_errors: List[BudgetExhausted] = []
        for route in routes:
            prof = route.profile
            try:
                self.quotas.reserve(prof.provider, prof.model)
            except BudgetExhausted as exc:
                errors.append(f"quota: {exc}")
                quota_errors.append(exc)
                continue
            wait = self._buckets[prof.provider].wait_time()
            if wait > 0:
                await asyncio.sleep(wait)
            started = time.monotonic()
            try:
                self._buckets[prof.provider].record()
                result = route.adapter.chat(
                    prof.model, list(messages), route.api_key,
                    max_tokens=max_tokens, **kwargs,
                )
                self.quotas.record(
                    prof.provider, prof.model,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
                self.audit.log(
                    "model.call",
                    task=task, provider=prof.provider, model=prof.model,
                    input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
                return result
            except AdapterError as exc:
                self.quotas.record(prof.provider, prof.model, failed=True)
                self.audit.log(
                    "model.error", task=task, provider=prof.provider, model=prof.model,
                    status=exc.status, retryable=exc.retryable, detail=str(exc)[:200],
                )
                errors.append(f"{prof.provider}/{prof.model}: {exc}")
                if not exc.retryable:
                    continue  # hard error: fall through immediately
                continue
        if quota_errors and len(quota_errors) == len(errors):
            # every route was refused by the quota governor: never a silent
            # paid upgrade, and the caller must see BudgetExhausted, not a
            # generic router failure
            raise quota_errors[0]
        raise RouterError("all routes failed: " + " | ".join(errors[:3]))

    async def stream(self, messages: Sequence[ChatMessage], **kwargs: Any):
        """Yield text chunks; falls back across routes like chat()."""
        result = await self.chat(messages, **kwargs)
        yield result.text

    async def models(self, provider: str) -> List[str]:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise RouterError(f"unknown provider {provider!r}")
        api_key = self._vault.get(provider) if self._vault is not None and self._vault.exists(provider) else ""
        return adapter.models(api_key)

    async def health(self) -> Dict[str, Any]:
        out = {"checked_at": _now_iso(), "providers": {}}
        for name, adapter in self._adapters.items():
            api_key = self._vault.get(name) if self._vault is not None and self._vault.exists(name) else ""
            try:
                out["providers"][name] = adapter.health(api_key)
            except Exception as exc:  # pragma: no cover - live network only
                out["providers"][name] = {"status": "error", "detail": str(exc)[:200]}
        return out

    async def embeddings(self, texts: List[str], **kwargs: Any) -> List[List[float]]:
        routes = self._routes("embeddings")
        if not routes:
            raise RouterError("no embedding route registered")
        route = routes[0]
        adapter = route.adapter
        if not hasattr(adapter, "embeddings"):
            raise RouterError(f"adapter {route.profile.provider} has no embeddings support")
        self.quotas.reserve(route.profile.provider, route.profile.model)
        return adapter.embeddings(texts, route.api_key, **kwargs)  # type: ignore[attr-defined]

    async def vision(self, prompt: str, image_ref: str, **kwargs: Any) -> ChatResult:
        return await self.chat(
            [ChatMessage(role="user", content=f"{prompt}\n[image: {image_ref}]")],
            capability="vision", task="vision", **kwargs,
        )

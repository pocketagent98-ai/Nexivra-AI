"""Provider adapters.

All provider-specific API calls live inside adapters (build spec section 8).
The gateway never talks to a provider directly. Keys are passed per call
from the vault and never stored on the adapter.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Protocol

from .types import _now_iso


class AdapterError(RuntimeError):
    def __init__(self, message: str, *, status: Optional[int] = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


@dataclass
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


class ProviderAdapter(Protocol):
    name: str

    def models(self, api_key: str) -> List[str]: ...

    def chat(self, model: str, messages: List[ChatMessage], api_key: str, *, stream: bool = False) -> Any: ...

    def health(self, api_key: str) -> Dict[str, Any]: ...


class OpenAICompatibleAdapter:
    """Works with any OpenAI-compatible /chat/completions + /models endpoint.

    Known-good targets (base_url values):
    - NVIDIA NIM : https://integrate.api.nvidia.com/v1   (key starts nvapi-)
    - z.ai       : https://api.z.ai/api/paas/v4

    Rate limits are configurable at the gateway; adapters assume nothing.
    """

    def __init__(self, name: str, base_url: str, *, timeout: float = 60.0) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, api_key: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers(api_key))
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:300]
            except Exception:  # pragma: no cover
                pass
            raise AdapterError(
                f"{self.name}: HTTP {exc.code} on {path}: {body}",
                status=exc.code,
                retryable=exc.code in RETRYABLE_STATUS,
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AdapterError(f"{self.name}: network error on {path}: {exc}", retryable=True) from exc
        except json.JSONDecodeError as exc:
            raise AdapterError(f"{self.name}: invalid JSON from {path}", retryable=False) from exc

    def models(self, api_key: str) -> List[str]:
        blob = self._request("GET", "/models", api_key)
        return sorted(m.get("id", "") for m in blob.get("data", []) if m.get("id"))

    def chat(
        self,
        model: str,
        messages: List[ChatMessage],
        api_key: str,
        *,
        stream: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> Any:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": bool(stream),
        }
        blob = self._request("POST", "/chat/completions", api_key, payload)
        if stream:
            return self._iter_stream_chunks(blob)
        choice = (blob.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content")) or ""
        usage = blob.get("usage") or {}
        return ChatResult(
            text=text,
            provider=self.name,
            model=model,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            raw=blob,
        )

    def _iter_stream_chunks(self, blob: Dict[str, Any]) -> Iterator[str]:
        # Adapters that cannot stream return the whole payload as one chunk.
        choice = (blob.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content")) or blob.get("content") or ""
        yield text

    def health(self, api_key: str) -> Dict[str, Any]:
        started = time.monotonic()
        ok = bool(self.models(api_key))
        return {
            "provider": self.name,
            "status": "ok" if ok else "degraded",
            "checked_at": _now_iso(),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }


class StaticAdapter:
    """Deterministic in-memory adapter for tests and the offline demo.

    ``script`` maps a substring of the last user message to a canned reply;
    ``default`` answers everything else. This keeps the whole pipeline —
    plan, research, verification, synthesis — testable with zero network.
    """

    def __init__(self, name: str = "static", script: Optional[Dict[str, str]] = None, default: str = "ok") -> None:
        self.name = name
        self.script = script or {}
        self.default = default
        self.calls: List[Dict[str, Any]] = []

    def models(self, api_key: str) -> List[str]:
        return ["static-1"]

    def chat(self, model: str, messages: List[ChatMessage], api_key: str, *, stream: bool = False, **_: Any) -> ChatResult:
        self.calls.append({"model": model, "messages": [m.role for m in messages]})
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        text = self.default
        for needle, reply in self.script.items():
            if needle in last_user:
                text = reply
                break
        approx_in = sum(len(m.content) for m in messages) // 4
        approx_out = len(text) // 4
        return ChatResult(
            text=text, provider=self.name, model=model,
            input_tokens=approx_in, output_tokens=approx_out,
        )

    def health(self, api_key: str) -> Dict[str, Any]:
        return {"provider": self.name, "status": "ok", "checked_at": _now_iso()}


NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"

NIM_KEY_PREFIX = "nvapi-"
KEY_PREFIXES = {"nvidia": NIM_KEY_PREFIX, "zai": ""}


def looks_like_key(provider: str, api_key: str) -> bool:
    """Cheap sanity check used by connection tests — never a security control."""
    prefix = KEY_PREFIXES.get(provider)
    return bool(api_key) and (prefix is None or api_key.startswith(prefix))

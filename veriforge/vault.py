"""ProviderVault — encrypted server-side storage for provider API keys.

Guarantees (per build spec section 9/12):
- keys are never hardcoded, never logged, never returned to the client
  after storage (``masked()`` gives only a preview);
- encrypted at rest with Fernet (AES-128-CBC + HMAC), master key taken from
  the environment (VAULT_MASTER_KEY, urlsafe-base64 32 bytes);
- supports store / test / rotate / remove;
- test_connection performs a real call only through the adapter layer and
  reports health, never the secret itself.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Callable, Dict, Optional

from cryptography.fernet import Fernet

from .types import _now_iso


class VaultError(RuntimeError):
    pass


def _load_master_key() -> bytes:
    raw = os.environ.get("VAULT_MASTER_KEY", "")
    if raw:
        try:
            key = base64.urlsafe_b64decode(raw.encode())
            if len(key) != 32:
                raise VaultError("VAULT_MASTER_KEY must decode to exactly 32 bytes")
            return key
        except Exception as exc:
            raise VaultError(f"invalid VAULT_MASTER_KEY: {exc}") from exc
    # Dev convenience: a fresh ephemeral key. Data does not survive restarts.
    return Fernet.generate_key()


class ProviderVault:
    """Server-side secret store. One instance owns one JSON file."""

    def __init__(self, path: Optional[Path] = None, *, master_key: Optional[bytes] = None) -> None:
        self._path = Path(path) if path else None
        self._fernet = Fernet(master_key if master_key is not None else _load_master_key())
        self._records: Dict[str, Dict[str, str]] = {}
        if self._path and self._path.exists():
            self._load()

    # -- persistence ---------------------------------------------------

    def _load(self) -> None:
        blob = json.loads(self._path.read_text() or "{}")  # type: ignore[union-attr]
        for name, rec in blob.items():
            self._records[name] = {
                "added_at": rec.get("added_at", ""),
                "rotated_at": rec.get("rotated_at", ""),
                "cipher": rec["cipher"],
            }

    def _save(self) -> None:
        if not self._path:
            return
        self._path.write_text(json.dumps(self._records, indent=2))

    # -- operations ------------------------------------------------------

    def store(self, provider: str, api_key: str, *, allow_overwrite: bool = True) -> None:
        if not api_key or not isinstance(api_key, str):
            raise VaultError("api_key must be a non-empty string")
        if provider in self._records and not allow_overwrite:
            raise VaultError(f"key for {provider!r} already stored")
        self._records[provider] = {
            "added_at": _now_iso(),
            "rotated_at": "",
            "cipher": self._fernet.encrypt(api_key.encode()).decode(),
        }
        self._save()

    def rotate(self, provider: str, new_api_key: str) -> None:
        if provider not in self._records:
            raise VaultError(f"no key stored for {provider!r}")
        self._records[provider] = {
            "added_at": self._records[provider]["added_at"],
            "rotated_at": _now_iso(),
            "cipher": self._fernet.encrypt(new_api_key.encode()).decode(),
        }
        self._save()

    def remove(self, provider: str) -> bool:
        existed = self._records.pop(provider, None) is not None
        self._save()
        return existed

    def exists(self, provider: str) -> bool:
        return provider in self._records

    def get(self, provider: str) -> str:
        """Secret access for the server-side adapter layer ONLY. Never log
        the return value; never send it to a client."""
        rec = self._records.get(provider)
        if rec is None:
            raise VaultError(f"no key stored for {provider!r}")
        return self._fernet.decrypt(rec["cipher"].encode()).decode()

    def masked(self, provider: str) -> Optional[str]:
        """Safe preview for UI: first 4 characters + ellipsis, or None."""
        rec = self._records.get(provider)
        if rec is None:
            return None
        try:
            secret = self._fernet.decrypt(rec["cipher"].encode()).decode()
        except Exception:  # pragma: no cover - tampered file
            return "<undecryptable>"
        if len(secret) <= 6:
            return "***"
        return secret[:4] + "***"

    def test_connection(self, provider: str, tester: Callable[[str], bool]) -> Dict[str, object]:
        """Run a caller-supplied health check (e.g. adapter.models()) using
        the stored key. Returns health only — the secret never leaves."""
        try:
            ok = tester(self.get(provider))
        except VaultError:
            return {"provider": provider, "status": "no_key"}
        except Exception as exc:  # tester itself failed (network, auth, ...)
            return {"provider": provider, "status": "error", "detail": str(exc)[:200]}
        return {"provider": provider, "status": "ok" if ok else "failed"}

    def __repr__(self) -> str:  # never leak secrets through repr either
        return f"ProviderVault(providers={sorted(self._records)}, path={self._path})"

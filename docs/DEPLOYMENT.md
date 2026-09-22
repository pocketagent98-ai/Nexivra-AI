# Deployment

## Status

v0.2.0 is a library + CLI-level core. It is NOT a hosted product yet.
There is no multi-tenant server, no user accounts, and no production
deployment. The instructions below are for local/evaluation use and for
the planned single-operator deployment.

## Requirements

- Python 3.11+
- `pip install -e ".[dev]"` (runtime: `cryptography`; dev: pytest, pytest-asyncio)

## Local run

```bash
python -m pytest               # 104 offline tests
python examples/demo_offline.py # full pipeline, no keys needed
```

## Environment variables

| Variable | Purpose |
|---|---|---n| `VAULT_MASTER_KEY` | urlsafe-base64 32-byte Fernet master key for the encrypted vault. If unset, an ephemeral per-process key is generated (dev only — stored keys do not survive restarts). Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `NEXIVRA_LOCAL_MODEL` | Path to the local Qwen3-0.6B GGUF file (see docs/LOCAL-AI.md). |
| `NEXIVRA_DEVICE_PROFILE` | `lite` \| `balanced` \| `auto` device profile (see docs/MOBILE.md). |

API keys are NOT environment configuration — they live in the vault,
entered through the official connect flow (see docs/NVIDIA-NIM.md).

## Single-operator deployment sketch

```
[Operator] -> app process
              |- UniversalModelGateway (adapters: nvidia, zai, ...)
              |- ProviderVault (encrypted JSON on a private volume)
              |- QuotaGovernor (budgets configured per provider)
              |- AuditLogger (JSONL on a private volume)
              |- ResearchEngine (bounded runs)
```

Checklist before any public exposure:

1. Per-user isolation and authentication (not yet implemented — do not
   expose to multiple users).
2. Request rate limiting at the HTTP layer.
3. Vault master key from a secret manager, rotated.
4. Audit logs shipped to append-only storage.
5. Provider terms reviewed for proxying/commercial use (docs/PROVIDERS.md).
6. A public status page.

## What "production-ready" will require

Per the build spec: unit + integration + security + research-quality
tests passing in CI, a production build of the UI, and honest reporting
of what is not done. CI currently runs the offline suite
(.github/workflows/ci.yml).

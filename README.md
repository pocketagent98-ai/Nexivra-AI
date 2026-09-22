# VeriForge AI

**Research. Verify. Then act.**

VeriForge AI is an evidence-first autonomous research and agent platform.
It plans work, delegates research, gathers evidence, checks claims, detects
conflicts, maintains project memory, uses sandboxed tool boundaries, and
routes all model requests through a unified gateway.

Core workflow:

```
ASK → PLAN → RESEARCH → COLLECT EVIDENCE → CROSS-CHECK → VERIFY → SYNTHESIZE → ACT
```

> **Status: v0.1.0 — core pipeline, not production-ready.**
> The evidence pipeline (gateway, vault, quotas, evidence store, claims,
> contradiction detection, verification gate, research engine, memory,
> audit) is implemented and covered by 85 offline tests. The product UI,
> multi-provider OmniRoute adapter, and hosted deployment are on the
> roadmap. Do not treat this as a finished SaaS.

## What this repository contains

| Component | Where | What it does |
|---|---|---|
| `UniversalModelGateway` | `veriforge/gateway.py` | The single chokepoint for every model call: routing, fallback, per-provider rate pacing, capability filters (chat / embeddings / vision). Application code never talks to a provider directly. |
| `ProviderVault` | `veriforge/vault.py` | Encrypted (Fernet) server-side key storage: store / test / rotate / remove. Keys are never logged, never returned to a client after storage — UI sees only a masked preview. |
| `QuotaGovernor` | `veriforge/quotas.py` | Free-tier and budget governance: request/token budgets, wildcard per-provider budgets, paid models blocked unless explicitly enabled — never a silent paid upgrade. |
| `SourceRegistry` + `EvidenceStore` | `veriforge/evidence.py` | Every source tracked with URL, title, domain, publication date, access date, tier, content hash; evidence excerpts linked to exactly one source. |
| `ClaimRegistry` | `veriforge/claims.py` | Every important factual claim gets an internal record with support / conflict / freshness statuses. |
| `ContradictionDetector` | `veriforge/conflicts.py` | Rule-based, deterministic detection of disagreeing figures; conflicts are explained (dates, definitions, methodology, geography, authority), never silently resolved. |
| `VerificationEngine` | `veriforge/verify.py` | The verification gate: evidence coverage, conflict disclosure, freshness, unsupported-in-synthesis detection, tool-failure disclosure, full audit chain. |
| `ResearchEngine` | `veriforge/research.py` | Modes (Quick / Deep / Verified Deep / Autonomous / Research-to-Action), bounded runs, parallel researchers, claim extraction with corroboration merging, evidence-anchored synthesis. |
| SSRF guard | `veriforge/ssrf.py` | Every fetched URL is validated: private/loopback/link-local/metadata addresses, internal hostnames, odd ports and non-HTTP schemes are refused. |
| Prompt-injection defense | `veriforge/untrusted.py` | Retrieved content is untrusted data: instruction-shaped patterns are neutralized and fenced before entering any prompt. |
| `AuditLogger` | `veriforge/audit.py` | JSONL trail for the full chain answer → claim → evidence → source → task → model → timestamp, with secrets structurally masked out. |
| `ResearchMemory` | `veriforge/memory.py` | Per-project memory of prior runs and their verification outcomes. |

The companion repository [DeerFlow-2.5](https://github.com/pocketagent98-ai/DeerFlow-2.5)
(MIT, a fork of bytedance/deer-flow) provides the agent harness this
platform is designed to plug into: its NVIDIA NIM auto-discovery, z.ai
fallback, rate-limit-aware routing and tier-first ranking are preserved
there and reused through the gateway's provider adapters.

## Quick start

```bash
git clone https://github.com/pocketagent98-ai/VeriForge-AI.git
cd VeriForge-AI
pip install -e ".[dev]"

# run the whole test suite (offline, no API keys needed)
python -m pytest

# run the offline Verified-Deep demo (conflicting sources included)
python examples/demo_offline.py
```

The demo runs the full pipeline — plan, research, evidence collection,
claim extraction, contradiction detection, verification gate, synthesis —
against canned sources with a deterministic in-memory model, so you can
see exactly what VeriForge does without any keys.

## Design rules this code enforces

1. Evidence first. A claim without evidence stays `unverified` — uncertainty is never converted into fake certainty.
2. Conflicts are disclosed, never silently resolved.
3. Same-model verification is a separate verification stage, not "independent proof".
4. Retrieved content is untrusted data, never authority over system policy.
5. Keys are never hardcoded, never logged, never sent to a client.
6. Free-tier limits are configurable settings, not promises; paid usage must be explicitly enabled.
7. Every run is bounded (agents, steps, searches, wall time, output tokens).
8. A search snippet is not final evidence when the original page is available.
9. Third-party licenses and notices are preserved (see `THIRD-PARTY-NOTICES.md`).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Research pipeline](docs/RESEARCH.md)
- [Verification & evidence model](docs/VERIFICATION.md)
- [Security](docs/SECURITY.md)
- [Connecting NVIDIA NIM](docs/NVIDIA-NIM.md)
- [Providers](docs/PROVIDERS.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Privacy](docs/PRIVACY.md)

## License

VeriForge AI is proprietary software, published source-available under the
[VeriForge AI Proprietary License](LICENSE). Third-party components remain
under their own licenses — see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
VeriForge AI is an independent product and is not affiliated with
DeerFlow, ByteDance, Apodex, OmniRoute, FreeLLMAPI, NVIDIA, or z.ai.

## Roadmap

- [ ] OmniRoute integration as the primary gateway adapter
- [ ] Web UI: Home / Research / Projects / Agents / Sources / Verification / Files / Models / Usage / Vault / Settings
- [ ] Live search + fetch tools (SearXNG/DuckDuckGo, Crawl4AI) behind the SSRF guard
- [ ] Real provider adapters wired to the vault (NVIDIA NIM, z.ai free tier)
- [ ] Embedding-based source deduplication and memory retrieval
- [ ] Download/release artifacts and public status page

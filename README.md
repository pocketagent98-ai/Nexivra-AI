# Nexivra AI

**Research deeper. Verify evidence. Act with context.**

Nexivra AI is an evidence-first autonomous research and agent platform.
It plans work, delegates research, gathers evidence, checks claims, detects
conflicts, maintains project memory, uses sandboxed tool boundaries, and
routes all model requests through a unified gateway.

Core workflow:

```
ASK → PLAN → RESEARCH → COLLECT EVIDENCE → CROSS-CHECK → VERIFY → SYNTHESIZE → ACT
```

> **Status: v0.2.0 — core pipeline + local AI layer, not production-ready.**
> The evidence pipeline (gateway, vault, quotas, evidence store, claims,
> contradiction detection, verification gate, research engine, memory,
> audit) and the API-aware cloud/local loading gate are implemented and
> covered by 104 offline tests. The product UI, live OmniRoute adapter,
> and the real llama.cpp binding are on the roadmap. Do not treat this as
> a finished product.

## What this repository contains

| Component | Where | What it does |
|---|---|---|
| `UniversalModelGateway` | `nexivra/gateway.py` | The single chokepoint for every model call: routing, fallback, per-provider rate pacing, capability filters (chat / embeddings / vision). Application code never talks to a provider directly. |
| `ProviderVault` | `nexivra/vault.py` | Encrypted (Fernet) server-side key storage: store / test / rotate / remove. Keys are never logged, never returned to a client after storage — UI sees only a masked preview. |
| `QuotaGovernor` | `nexivra/quotas.py` | Free-tier and budget governance: request/token budgets, wildcard per-provider budgets, paid models blocked unless explicitly enabled — never a silent paid upgrade. |
| `SourceRegistry` + `EvidenceStore` | `nexivra/evidence.py` | Every source tracked with URL, title, domain, publication date, access date, tier, content hash; evidence excerpts linked to exactly one source. |
| `ClaimRegistry` | `nexivra/claims.py` | Every important factual claim gets an internal record with support / conflict / freshness statuses. |
| `ContradictionDetector` | `nexivra/conflicts.py` | Rule-based, deterministic detection of disagreeing figures; conflicts are explained (dates, definitions, methodology, geography, authority), never silently resolved. |
| `VerificationEngine` | `nexivra/verify.py` | The verification gate: evidence coverage, conflict disclosure, freshness, unsupported-in-synthesis detection, tool-failure disclosure, full audit chain. |
| `ResearchEngine` | `nexivra/research.py` | Modes (Quick / Deep / Verified Deep / Autonomous / Research-to-Action), bounded runs, parallel researchers, claim extraction with corroboration merging, evidence-anchored synthesis. |
| SSRF guard | `nexivra/ssrf.py` | Every fetched URL is validated: private/loopback/link-local/metadata addresses, internal hostnames, odd ports and non-HTTP schemes are refused. |
| Prompt-injection defense | `nexivra/untrusted.py` | Retrieved content is untrusted data: instruction-shaped patterns are neutralized and fenced before entering any prompt. |
| `AuditLogger` | `nexivra/audit.py` | JSONL trail for the full chain answer → claim → evidence → source → task → model → timestamp, with secrets structurally masked out. |
| `ResearchMemory` | `nexivra/memory.py` | Per-project memory of prior runs and their verification outcomes. |
| API-aware router | `nexivra/local.py` | The mandatory cloud-first loading gate: healthy authorized cloud API → use cloud, local model MUST NOT be loaded; no usable API → lazily load local Qwen3-0.6B (GGUF via llama.cpp); cloud recovers → resume cloud, unload local when safe. Classifies missing/invalid key, 429, 5xx, timeout, quota exhaustion, provider outage, network offline. |

The companion repository [DeerFlow-2.5](https://github.com/pocketagent98-ai/DeerFlow-2.5)
(MIT, a fork of bytedance/deer-flow) provides the agent harness this
platform is designed to plug into: its NVIDIA NIM auto-discovery, z.ai
fallback, rate-limit-aware routing and tier-first ranking are preserved
there and reused through the gateway's provider adapters.

## Quick start

```bash
git clone https://github.com/pocketagent98-ai/Nexivra-AI.git
cd Nexivra-AI
pip install -e ".[dev]"

# run the whole test suite (offline, no API keys needed)
python -m pytest            # 104 tests

# run the offline Verified-Deep demo (conflicting sources included)
python examples/demo_offline.py
```

The demo runs the full pipeline — plan, research, evidence collection,
claim extraction, contradiction detection, verification gate, synthesis —
against canned sources with a deterministic in-memory model, so you can
see exactly what Nexivra does without any keys.

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

## Local AI (offline / low connectivity)

Model path:

```
Cloud: DeerFlow → UniversalModelGateway → OmniRoute → authorized provider
Local: DeerFlow → UniversalModelGateway → llama.cpp → Qwen3-0.6B GGUF
```

- Primary local model: **Qwen3-0.6B** (Apache 2.0), quantized GGUF (Q4_0,
  listed around 429 MB — verify per build). Runtime: **llama.cpp** native —
  no Python/PyTorch/Transformers requirement on mobile.
- Optional emergency ultra-lite: SmolLM2-135M-Instruct (English-centric per
  its model card — optional, never the default). RWKV-4 169M is not used.
- The local model is lazy-loaded ONLY when no usable cloud API exists, and
  unloaded when the cloud recovers and generation is not in flight.
- Device profiles: Lite (2048-token context) / Balanced (4096) / Auto; RAM
  thresholds are deliberately not hardcoded.
- Never a silent switch to a paid API: if neither authorized cloud nor local
  model is usable, the request fails loudly.

Model honesty: the local model is a third-party model (Qwen3-0.6B) running
inside Nexivra AI — "the Nexivra AI assistant powered by Qwen3-0.6B in local
mode" — never "a proprietary Nexivra model".

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Research pipeline](docs/RESEARCH.md)
- [Verification & evidence model](docs/VERIFICATION.md)
- [Local AI (Qwen3-0.6B / llama.cpp)](docs/LOCAL-AI.md)
- [Mobile & low-end devices](docs/MOBILE.md)
- [OmniRoute integration](docs/OMNIROUTE.md)
- [Security](docs/SECURITY.md)
- [Connecting NVIDIA NIM](docs/NVIDIA-NIM.md)
- [Providers](docs/PROVIDERS.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Privacy](docs/PRIVACY.md)

## License

Nexivra AI is proprietary software, published source-available under the
[Nexivra AI Proprietary License](LICENSE). Third-party components remain
under their own licenses — see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
Nexivra AI is an independent product and is not affiliated with
DeerFlow, ByteDance, Apodex, OmniRoute, FreeLLMAPI, NVIDIA, or z.ai.

## Roadmap

- [ ] OmniRoute integration as the primary gateway adapter
- [ ] Real llama.cpp binding for the local runtime (native/Android path)
- [ ] Web UI: Home / Research / Projects / Agents / Sources / Verification / Files / Models / Usage / Vault / Settings
- [ ] Live search + fetch tools (SearXNG/DuckDuckGo, Crawl4AI) behind the SSRF guard
- [ ] Real provider adapters wired to the vault (NVIDIA NIM, z.ai free tier)
- [ ] Embedding-based source deduplication and memory retrieval
- [ ] Download/release artifacts and public status page

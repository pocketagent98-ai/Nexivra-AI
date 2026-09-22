# Changelog

All notable changes to Nexivra AI are documented here.

## [0.2.0] — 2026-09-22 (Nexivra update)

Product renamed VeriForge AI → **Nexivra AI** (working name; verify
trademark/domain availability before commercial use).

### Added
- `nexivra/local.py`: the API-aware cloud/local loading gate.
  - `APIAwareRouter`: healthy authorized cloud API → cloud (local model
    MUST NOT be loaded); no usable API → lazy-load local Qwen3-0.6B;
    cloud recovers → resume cloud and unload local when safe.
  - Failure classification: missing key, invalid key (401/403), 429,
    5xx, timeout, quota exhaustion, provider outage, network offline.
  - `DeviceProfile` (Lite / Balanced / Auto): context 2048–4096 tokens,
    conservative generation, no hardcoded RAM thresholds.
  - `LocalModelSpec` entries for Qwen3-0.6B (primary, Q4_0 GGUF) and
    optional SmolLM2-135M-Instruct ultra-lite; RWKV-4 169M excluded.
  - `StubLocalRuntime` for offline tests; `LocalModelUnavailable` raised
    instead of ever silently switching to a paid API.
- 19 new offline tests for the loading gate (cloud routing, local
    routing, switching, unload-when-safe and while-busy deferral, key
    failure, 429, timeout, quota, lazy loading, probe interval).
- Docs: `docs/LOCAL-AI.md`, `docs/MOBILE.md`, `docs/OMNIROUTE.md`.
- Third-party notices extended with Qwen3-0.6B, llama.cpp and SmolLM2
  entries plus a model-honesty note (third-party models are never called
  proprietary Nexivra models).

### Changed
- Full rebrand VeriForge → Nexivra across package, docs and packaging.
- Deterministic wall-time truncation test.

## [0.1.0] — 2026-09-22

Initial public core release of the evidence pipeline.

### Added
- `UniversalModelGateway`: single chokepoint for model access — routing,
  fallback chain, per-provider rate pacing (configurable RPM), capability
  filters (chat / embeddings / vision), quota enforcement, audit logging.
- Provider adapters: OpenAI-compatible adapter (NVIDIA NIM, z.ai target
  URLs) and a deterministic `StaticAdapter` for offline runs/tests.
- `ProviderVault`: Fernet-encrypted server-side key storage with masked
  previews, rotation, removal, connection testing — secrets never logged
  or returned to clients.
- `QuotaGovernor`: request/token budgets (exact or per-provider
  wildcard), paid-model blocking without explicit opt-in, usage reporting.
- Evidence layer: `SourceRegistry` (URL + content-hash dedup, tiers,
  dates) and `EvidenceStore` (excerpts with extracted measurements).
- `ClaimRegistry` with the full status set (supported /
  partially_supported / conflicting / unverified / outdated / opinion /
  inference).
- `ContradictionDetector`: deterministic numeric conflict detection with
  structured explanations (dates, publishers, methodology, authority);
  conflicts disclosed, never silently resolved.
- `VerificationEngine` gate: evidence coverage, conflict disclosure,
  freshness window, unsupported-in-synthesis detection, tool-failure
  disclosure, audit chain.
- `ResearchEngine`: Quick / Deep / Verified Deep / Autonomous /
  Research-to-Action modes, bounded runs (agents, steps, searches, wall
  time, output tokens), parallel researchers, corroboration merging,
  evidence-anchored synthesis, truncated-run disclosure.
- SSRF guard for every fetched URL; prompt-injection defense
  (neutralize + fence) for all retrieved content.
- `ResearchMemory` project memory; JSONL `AuditLogger` with structural
  secret masking.
- 85 offline tests (unit + research-quality: conflicting sources,
  outdated sources, single-source caution, injection, tool failures).
- Documentation set: architecture, research, verification, security,
  NVIDIA NIM connection, providers, deployment, privacy; third-party
  notices.

### Not yet implemented (roadmap)
- OmniRoute integration as the primary gateway adapter; live search and
  fetch tool implementations; web UI; multi-tenant isolation; sandboxed
  action execution; public website and release artifacts.

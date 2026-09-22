# Architecture

## Model path

```
Application (ResearchEngine, future DeerFlow harness UI)
   |
   v
UniversalModelGateway            <- single chokepoint
   |
   +-- provider adapter A (e.g. NVIDIA NIM, OpenAI-compatible)
   +-- provider adapter B (e.g. z.ai, OpenAI-compatible)
   +-- (planned) OmniRoute adapter -> providers
   +-- fallback chain ...
```

Rules:

- Application code NEVER calls a provider directly; all calls go through
  `UniversalModelGateway`.
- Provider-specific API calls live only inside adapters.
- FreeLLMAPI is an optional adapter/reference — never a second router
  stacked under OmniRoute. Do not build two independent smart routers on
  top of each other.
- Version 1 targets one primary LLM family through the gateway. This is a
  multi-agent architecture, not a multi-model architecture; extension
  points exist for a secondary verifier, vision, embeddings and local
  fallback models.

## Research pipeline

```
Question
  -> Plan (planner role, via gateway)
  -> Task DAG (bounded by RunLimits)
  -> Parallel researchers (bounded concurrency)
  -> Source retrieval (SearchTool; every URL SSRF-checked)
  -> Fetch (FetchTool; content defused + fenced as untrusted data)
  -> Evidence extraction (sentences carrying measurements)
  -> Claim extraction (corroboration merging: same-metric evidence joins one claim)
  -> Verification (coverage, conflicts, freshness, synthesis check)
  -> Conflict detection (rule-based, deterministic)
  -> Synthesis (evidence-anchored; statuses disclosed)
  -> [Research-to-Action mode] execute ONLY approved actions
```

## Component map

| Concern | Module | Notes |
|---|---|---|
| Types / records | `veriforge/types.py` | Claim, Evidence, Source, ClaimStatus, SourceTier |
| Model access | `veriforge/adapters.py`, `veriforge/gateway.py` | OpenAI-compatible adapter; StaticAdapter for deterministic offline runs |
| Secrets | `veriforge/vault.py` | Fernet-encrypted JSON store; masked previews only |
| Budgets | `veriforge/quotas.py` | Exact or per-provider wildcard budgets; paid models opt-in |
| Evidence | `veriforge/evidence.py` | Source dedup by URL + content hash |
| Claims | `veriforge/claims.py` | Status updates flow only through the verifier |
| Contradictions | `veriforge/conflicts.py` | Unit-family grouping, tolerance-based comparison |
| Verification gate | `veriforge/verify.py` | See docs/VERIFICATION.md |
| Orchestration | `veriforge/research.py` | Modes + limits |
| Memory | `veriforge/memory.py` | Per-project run summaries |
| Audit | `veriforge/audit.py` | JSONL, secrets masked structurally |
| Untrusted content | `veriforge/untrusted.py` | Neutralize + fence |
| Network safety | `veriforge/ssrf.py` | assert_safe_url on every fetch |

## Audit chain

Every verified answer can be replayed:

```
answer section -> claim -> evidence -> source -> research task -> model/provider -> timestamp
```

The `AuditLogger` records `model.call`, `model.error`, `quota.reserve`,
`claim.status`, `verification.gate`, `research.done` events. Secret values
cannot appear in the trail: the `mask()` helper collapses any
credential-named field before serialization.

## Companion harness

The DeerFlow-2.5 fork (MIT) remains the agent harness this platform is
designed to plug into: planning, sub-agents, memory, sandbox, files, tools,
skills, MCP and long-running execution. Its provider brain (NVIDIA NIM
auto-discovery, z.ai fallback, rate-limit-aware retry, tier-first ranking,
circuit breaker) is preserved there and reused through adapters — never
duplicated here.

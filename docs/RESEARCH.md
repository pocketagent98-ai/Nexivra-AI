# Research pipeline

## Modes

| Mode | Budget | Use |
|---|---|---|
| Quick | ≤2 agents, ≤3 searches, 120 s | fast first-pass answers |
| Deep | 6 agents, 30 searches, 15 min | wider source coverage |
| Verified Deep | 8 agents, 40 searches, 20 min | + claim verification + contradiction checks (default) |
| Autonomous | 12 agents, 100 searches, 30 min | long-running but bounded |
| Research-to-Action | per limits | research first, then execute only approved actions |

Every run is bounded by `RunLimits` (max_agents, max_steps, max_searches,
max_wall_time_seconds, max_output_tokens). More agents are not
automatically better. If the wall-clock budget is exceeded the run ends
with `truncated=True` and that fact is disclosed in the report.

## Agent roles

planner · researcher · source analyst · claim analyst · verifier ·
contradiction analyst · synthesizer · executor

## Evidence collection

1. Search hits are fetched through `FetchTool` only after `assert_safe_url`.
2. Retrieved content is **untrusted data**: it is neutralized and fenced
   (`veriforge/untrusted.py`) before anything downstream sees it.
3. Sources are recorded with URL, title, domain, publication date, access
   date, type, tier and content hash; duplicates by URL or content hash
   collapse to one source.
4. Sentences that carry quantitative measurements become evidence records
   linked to exactly one source.

## Claim extraction and corroboration merging

Evidence records that discuss the same metric (same unit family, e.g. two
revenue figures in millions) merge into a single claim. This lets the
verifier see corroboration (two sources, same figure → supported) and
contradiction (two sources, different figures → conflicting) instead of
two isolated half-claims.

## Synthesis

Synthesis is evidence-anchored and deterministic in v0.1:

- supported claims are stated with their source domains;
- single-source claims are stated with a caution;
- conflicting claims are shown under "CONFLICTING EVIDENCE" with the
  conflict explanation;
- unverified/outdated claims are listed, not asserted;
- if no evidence was collected, the answer says so.

## What we do NOT claim

- Same-model verification is a separate verification stage, not independent
  model diversity or "independent proof".
- No 100% accuracy; not everything is always verified.
- No unlimited or permanent free inference — see docs/PROVIDERS.md.

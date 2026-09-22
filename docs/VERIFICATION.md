# Verification & evidence model

## Claim record

Every important factual claim carries an internal record:

```json
{
  "claim": "Example claim",
  "sources": ["ev_123", "ev_456"],
  "support_status": "supported",
  "conflict_status": "none",
  "freshness": "recent",
  "verification_notes": "Supported by two sources."
}
```

Allowed support statuses:

| Status | Meaning |
|---|---|
| `supported` | ≥ 2 independent sources agree |
| `partially_supported` | exactly one independent source — stated with caution |
| `conflicting` | sources disagree; the disagreement is explained, not resolved |
| `unverified` | no evidence attached |
| `outdated` | supporting sources are older than the freshness window (default 3 years) |
| `opinion` | subjective statement |
| `inference` | derived, not directly evidenced |

Uncertainty is never converted into fake certainty.

## Source tiers (preference order)

1. official/primary
2. government/institutional
3. academic
4. company documentation
5. reputable secondary reporting
6. community material

A search snippet is not final evidence when the original page is available
(`Source.is_snippet` marks the distinction).

## Contradiction detection

The `ContradictionDetector` is deliberately rule-based and deterministic:

- measurements are extracted from evidence text (value + unit family);
- comparable readings are grouped by unit family;
- any value pair differing beyond a 2% relative tolerance is a numeric
  conflict;
- conflicts are explained by checking publication dates, publisher
  domains, methodology/definitions and source authority — in that order;
- conflicting figures are presented together in the final answer. The
  system never silently selects one.

## The verification gate

Before a final report is returned:

```
Every major claim has evidence?                no  -> mark unverified / revise
Conflicting sources?                            yes -> explain the conflict
Fresh enough?                                   no  -> mark outdated/uncertain
Synthesis introduced unsupported claims?        yes -> rewrite
Tool failure?                                   yes -> disclose limitation
Then -> FINAL
```

`VerificationReport` carries per-claim verdicts, the sentences found in
the synthesis that trace to no registered claim, tool failures, and the
gate decision log.

## Audit trail

answer section → claim → evidence → source → research task → model/provider → timestamp

All of it lands in the JSONL `AuditLogger` with secrets structurally
masked. `python examples/demo_offline.py` prints a compact example of the
full chain.

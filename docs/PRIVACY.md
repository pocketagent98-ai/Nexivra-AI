# Privacy

## What Nexivra AI stores

- Research runs: the question, the plan, the sources (URL, title, domain,
  publication/access dates, tier, content hash), evidence excerpts,
  claims and their verification statuses, and the final synthesis.
- Audit events: timestamps, task/provider/model identifiers, token counts.
  Secret values are structurally masked and cannot appear in the trail.
- Project memory: compact run summaries per project (question, statuses,
  source URLs). Bodies and secrets are not stored.
- Provider keys (if you connect one): encrypted at rest, never returned to
  a client, removable and rotatable at any time.

## What it does not do

- It does not read browser data, cookies, saved passwords or session
  tokens.
- It does not send your research content to any provider other than
  through the model calls you configure (and whose keys you own).
- It does not sell or share data. There is no analytics or telemetry in
  this repository.

## Your control

- Remove a provider key: `vault.remove(provider)`.
- Delete a project's memory: delete its entry from the memory file.
- Free-tier usage is visible in every report (`usage`) — nothing runs on
  paid inference unless you explicitly enable it.

## Disclosure duty

Research reports disclose tool failures, conflicting evidence, unverified
claims and truncated runs. The system never presents an uncertain finding
as verified fact.

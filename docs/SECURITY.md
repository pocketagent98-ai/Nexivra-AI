# Security

## Secrets / Vault

- Provider keys are stored server-side, encrypted at rest with Fernet
  (AES-128-CBC + HMAC). Master key comes from `VAULT_MASTER_KEY`
  (urlsafe-base64, 32 bytes) — never hardcoded.
- Keys are never logged: the audit trail masks credential-named fields and
  known key prefixes (`nvapi-`, `sk-`, `Bearer `) before serialization.
- After storage a key is never returned to the browser — the UI gets
  `vault.masked(provider)` (first 4 chars + `***`).
- `vault.test_connection()` reports health only, never the secret.
- Rotation and removal are first-class operations.

## Key handling rules (hard)

Never: read browser passwords, read cookies, extract session tokens,
scrape local storage, bypass MFA/CAPTCHA, bypass account or region
controls, or use hidden endpoints to obtain credentials. Only official
authorization/key flows (see docs/NVIDIA-NIM.md).

## Network egress

- Every fetched URL passes `assert_safe_url`: only http/https, no
  private/loopback/link-local/multicast/reserved targets, no IPv4-mapped
  IPv6 bypass, no `localhost`/`.local`/`.internal` hosts, no cloud
  metadata endpoints, restricted ports, length caps.
- When DNS resolution is enabled, resolved addresses are re-checked — a
  hostname that resolves to an internal address is refused.

## Untrusted content (prompt-injection defense)

Web pages, PDFs, repositories, search results and uploaded documents are
untrusted data. They can be evidence; they are never authority over system
policy. `defuse()` neutralizes instruction-shaped patterns ("ignore all
previous instructions", fake `system:` role markers, credential-shaped
strings), wraps the content in data fences, and truncates huge inputs
before anything downstream sees it.

## Quotas and paid usage

- Free-tier budgets are configurable settings (requests, input tokens,
  output tokens; exact or per-provider wildcard).
- A paid model raises `PaidModelBlocked` unless it was explicitly enabled
  with `QuotaGovernor.allow_paid(...)`.
- When the free budget is exhausted the caller receives
  `BudgetExhausted` — the system waits, asks for another authorized key,
  or stops. It never silently switches to paid usage.

## Rate limits

Per-provider pacing (RPM) is a profile setting at the gateway, not a
hardcoded promise. The 40 RPM NVIDIA NIM free-tier assumption from the
DeerFlow-2.5 fork is treated as configurable and to be verified against
the live provider.

## Remaining hardening work (honest list)

The following items from the build spec are NOT yet implemented and are on
the roadmap: per-user isolation for a multi-tenant server, command/tool
permission enforcement beyond action allow-lists, sandbox isolation for
executed actions, and full request-budget middleware. Do not run this
code as a multi-user service yet.

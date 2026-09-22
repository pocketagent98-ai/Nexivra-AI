# Connecting NVIDIA NIM

## Flow (official, user-mediated)

```
[ Connect NVIDIA NIM ]
        |
        v
Official NVIDIA account/API-key page (build.nvidia.com)
        |
        v
User signs in
        |
        v
User completes the official "Get API Key" flow (key starts with nvapi-)
        |
        v
User returns to the app
        |
        v
Secure key connection / paste
        |
        v
Encrypted Vault (server-side, Fernet)
        |
        v
[ Test Connection ]  ->  model discovery
```

If an official OAuth/device flow exists for the exact NVIDIA service
being used, use it. Until then, use this user-mediated key-entry flow —
the app never touches the browser, never reads cookies, sessions or
passwords, and never bypasses MFA/CAPTCHA.

## After connecting

1. `vault.store("nvidia", key)` — encrypted at rest.
2. `vault.test_connection("nvidia", tester)` with a tester that calls
   `gateway.models("nvidia")` — reports health only.
3. Model discovery reuses the DeerFlow-2.5 provider work: live
   `/v1/models` listing on `https://integrate.api.nvidia.com/v1`
   (OpenAI-compatible), so every model available on your key can be
   registered as a gateway profile.

## Rules

- The key is never hardcoded, never logged, never returned to the client
  after storage.
- The 40 requests/minute free-tier pacing from the DeerFlow-2.5 fork is a
  *configurable* `rpm_limit` on the gateway profile — verify the live
  provider limit instead of treating it as permanent.
- Free serverless credits are observations at a point in time, not
  guarantees. When the free budget is exhausted the system stops and
  asks; it never silently bills.

## Reference

NVIDIA NIM API quickstart: https://docs.api.nvidia.com/nim/docs/api-quickstart
(Get API Key on build.nvidia.com.)

z.ai keys are connected the same way (`vault.store("zai", key)`, base URL
`https://api.z.ai/api/paas/v4`) and the same rules apply.

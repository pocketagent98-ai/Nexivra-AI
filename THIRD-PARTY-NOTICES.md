# Third-Party Notices

VeriForge AI is an independent proprietary product that integrates and
interoperates with third-party open-source software and model
technologies. Third-party components remain under their respective
licenses. The entries below record attribution and license information.

## Components integrated or referenced

| Component | Version / commit | Source | License | Shipped in this repo? | Local modifications |
|---|---|---|---|---|---|
| DeerFlow (upstream harness) | commit `437959b` (via pocketagent98-ai/DeerFlow-2.5 fork) | https://github.com/bytedance/deer-flow | MIT | No — companion repo | Fork adds NVIDIA NIM discovery, z.ai fallback, tier-first ranking, circuit breaker |
| OmniRoute | latest main (referenced) | https://github.com/diegosouzapw/OmniRoute | MIT | No — planned gateway adapter | None |
| FreeLLMAPI | latest main (referenced) | https://github.com/tashfeenahmed/freellmapi | MIT | No — optional adapter/reference | None |
| cryptography (Python package) | ≥ 42.0 | https://github.com/pyca/cryptography | Apache-2.0 OR BSD-3-Clause | Yes — runtime dependency (pip) | None |
| pytest / pytest-asyncio | ≥ 8.0 / ≥ 0.23 | https://github.com/pytest-dev/pytest | MIT | Dev dependency only | None |

## Notes

- Upstream DeerFlow is MIT licensed, Copyright (c) 2025 Bytedance Ltd.
  and/or its affiliates, Copyright (c) 2025-2026 DeerFlow Authors. Its
  license and credits are preserved in the companion DeerFlow-2.5
  repository.
- NVIDIA NIM and z.ai are third-party services accessed only through
  their official APIs with user-provided keys. No affiliation, endorsement,
  or redistribution of their models is claimed.
- Free-tier capacity figures quoted anywhere in VeriForge AI documentation
  are observations at a point in time, not guarantees; provider catalogs,
  quotas and terms change.

## VeriForge AI's own code

Copyright © 2026 pocketagent98-ai. All rights reserved.
Covered by the VeriForge AI Proprietary License (see LICENSE). This notice
applies only to code that is original to this repository and legally
entitled to proprietary treatment; third-party code keeps its own license.

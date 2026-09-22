# Third-Party Notices

Nexivra AI is an independent proprietary product that integrates and
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
| Qwen3-0.6B (model) | current release; Q4_0 GGUF listed ~429 MB | https://huggingface.co/Qwen | Apache-2.0 | No — user-supplied GGUF, never committed | None |
| llama.cpp (runtime) | current release | https://github.com/ggml-org/llama.cpp | MIT | No — native runtime bound by the app | None |
| SmolLM2-135M-Instruct (model, optional) | current release | https://huggingface.co/HuggingFaceTB | Apache-2.0 | No — optional ultra-lite, user-supplied | None |

## Notes

- Upstream DeerFlow is MIT licensed, Copyright (c) 2025 Bytedance Ltd.
  and/or its affiliates, Copyright (c) 2025-2026 DeerFlow Authors. Its
  license and credits are preserved in the companion DeerFlow-2.5
  repository.
- NVIDIA NIM and z.ai are third-party services accessed only through
  their official APIs with user-provided keys. No affiliation, endorsement,
  or redistribution of their models is claimed.
- Free-tier capacity figures quoted anywhere in Nexivra AI documentation
  are observations at a point in time, not guarantees; provider catalogs,
  quotas and terms change.
- Model honesty: third-party models (Qwen3-0.6B, SmolLM2) running inside
  the product are NOT proprietary Nexivra models. Correct attribution is
  "Nexivra AI assistant powered by Qwen3-0.6B in local mode".

## Nexivra AI's own code

Copyright © 2026 pocketagent98-ai. All rights reserved.
Covered by the Nexivra AI Proprietary License (see LICENSE). This notice
applies only to code that is original to this repository and legally
entitled to proprietary treatment; third-party code keeps its own license.

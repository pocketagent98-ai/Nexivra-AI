# Mobile & low-end devices

## Device profiles

`DeviceProfile` (nexivra/local.py) defines three profiles:

| Profile | Context window | Max generation | Intended for |
|---|---|---|---|
| Lite | 2048 tokens | 256 tokens | very constrained devices |
| Balanced | 4096 tokens | 1024 tokens | typical phones |
| Auto | 4096 tokens (runtime-detected) | 1024 tokens | let the app decide |

## Rules

- Small GGUF quantization first (Q4_0 for Qwen3-0.6B).
- Lazy loading: the local model is only loaded when no usable cloud API
  exists (see docs/LOCAL-AI.md), and only once.
- Configurable context per profile; start around 2048–4096 tokens on
  low-resource devices and reduce context under memory pressure.
- Unload the model when it is no longer needed (cloud recovered, or the
  app goes idle).
- Conservative generation lengths on constrained profiles.
- CPU-first fallback: hardware acceleration is enabled only when the
  specific device/accelerator has actually been tested.
- Do NOT hard-code RAM thresholds until real target-device benchmarks
  exist — profile selection should use measured capability detection,
  not guessed cutoffs.

## Runtime shape on device

```
native app (Kotlin/Swift/…)
  + llama.cpp native runtime (official Android binding path)
  + Qwen3-0.6B Q4_0 GGUF (~429 MB listed; verify per build)
```

No Python, PyTorch, or Transformers on the mobile path. This repository
provides the orchestration logic (`APIAwareRouter`, device profiles,
loading gate) behind stable interfaces so the native binding can be
implemented against them.

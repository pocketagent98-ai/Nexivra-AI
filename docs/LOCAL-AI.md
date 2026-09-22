# Local AI — Qwen3-0.6B via llama.cpp

Nexivra AI offers lightweight local AI for offline and low-connectivity
use. Local mode is a **fallback**, never the default when a healthy
authorized cloud API exists.

## Model path

```
Cloud: DeerFlow -> UniversalModelGateway -> OmniRoute -> authorized provider
Local: DeerFlow -> UniversalModelGateway -> llama.cpp -> Qwen3-0.6B GGUF
```

## Models

| Model | License | Role | Notes |
|---|---|---|---|
| Qwen3-0.6B | Apache 2.0 | primary local model | quantized GGUF build, Q4_0 listed around 429 MB — verify the exact conversion and size before shipping |
| SmolLM2-135M-Instruct | Apache 2.0 | optional emergency ultra-lite | primarily English per its model card — optional only, never the default worldwide model |
| RWKV-4 169M | — | not used | not suitable as the primary assistant |

Model honesty: these are third-party models. Correct wording is
"Nexivra AI assistant powered by Qwen3-0.6B in local mode", never
"a proprietary Nexivra model".

## Runtime

Use the **llama.cpp** native runtime with GGUF models. Do NOT require
Python, PyTorch or Transformers on mobile. The intended shape is:

```
native app + llama.cpp native runtime + GGUF model
```

In this repository the runtime is behind the `LocalRuntime` protocol
(`nexivra/local.py`); a native app binds it to llama.cpp's official
Android/native API, and tests use `StubLocalRuntime`.

## API-aware loading (mandatory)

```
START
  -> is a healthy authorized cloud API available?
     YES -> use cloud; the local model MUST NOT be loaded
     NO  -> lazily load local Qwen3-0.6B
  -> when the cloud becomes healthy again:
     resume cloud, unload the local model when safe
```

`APIAwareRouter` (nexivra/local.py) implements this gate:

- `route()` returns `"cloud"` or `"local"`; the local model loads lazily
  inside `route()` only, and only when the cloud is unusable.
- `report_cloud_failure(kind)` marks the cloud down; failure kinds:
  missing key, invalid key (401/403), 429, 5xx, timeout, quota
  exhaustion, provider outage, network offline.
- `probe_cloud()` re-checks health on an interval; on recovery the local
  model is unloaded when generation is not in flight ("when safe").
- `generate_local()` probes the cloud first and refuses if it recovered —
  local generation never continues after the cloud is back.
- Never a silent switch to a paid API: with no usable cloud API and no
  local model, the request raises `LocalModelUnavailable` loudly.

## Environment

| Variable | Purpose |
|---|---|
| `NEXIVRA_LOCAL_MODEL` | path to the Qwen3-0.6B GGUF file (e.g. `models/qwen3-0.6b-q4_0.gguf`) |
| `NEXIVRA_LOCAL_ULTRA_LITE` | optional SmolLM2 GGUF path for very constrained devices |
| `NEXIVRA_DEVICE_PROFILE` | `lite` / `balanced` / `auto` (see docs/MOBILE.md) |

The GGUF files are NOT committed to this repository — fetch them from
their official sources and verify the license and hash of the exact
build you ship.

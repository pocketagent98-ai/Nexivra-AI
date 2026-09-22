# Providers

## Model path

```
Application -> UniversalModelGateway -> adapter -> provider
```

The preferred production path adds OmniRoute as the primary gateway
adapter (planned):

```
DeerFlow harness -> UniversalModelGateway -> OmniRoute adapter -> provider
```

FreeLLMAPI stays an optional adapter/reference. Do not stack
FreeLLMAPI and OmniRoute as two independent routers — it adds failure
analysis complexity for no benefit.

## Adapter facts

`OpenAICompatibleAdapter` works with any OpenAI-compatible
`/chat/completions` + `/models` endpoint:

| Provider | Base URL | Key |
|---|---|---|
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `nvapi-...` from build.nvidia.com |
| z.ai | `https://api.z.ai/api/paas/v4` | from z.ai (free flash models) |

Registering a route:

```python
from veriforge.adapters import OpenAICompatibleAdapter
from veriforge.gateway import ModelProfile, UniversalModelGateway

gw = UniversalModelGateway(vault=vault, quotas=quotas, audit=audit)
gw.register_adapter(OpenAICompatibleAdapter("nvidia", "https://integrate.api.nvidia.com/v1"))
gw.add_profile(ModelProfile(provider="nvidia", model="my-model",
                            rpm_limit=40, priority=10))
```

## One-LLM strategy

Version 1 uses one primary LLM family through the gateway:

```
Planner       -> one LLM
Researcher A  -> one LLM
Researcher B  -> one LLM
Verifier      -> one LLM
Synthesizer   -> one LLM
Executor      -> one LLM
```

This is a multi-agent architecture, but not a multi-model architecture.
Same-model verification is a separate verification stage, not independent
model diversity. Extension points exist for a secondary verifier, vision,
embeddings, speech and local fallback models.

## Free inference rules

- Never promise unlimited free inference.
- Never promise a permanent fixed token budget.
- Never silently switch to paid usage — `QuotaGovernor.assert_paid_allowed`
  gates every paid model behind explicit enablement.
- Expose quota status (`quotas.usage()` in every research report).
- Stop or ask for another authorized key when the free budget is
  exhausted.

## Public SaaS warning

A personal free API key must not automatically become the backend for
thousands of public users. Before any public SaaS use, check each
provider's current terms for proxying, redistribution, third-party
access, resale, commercial use, automated querying and production usage.
For a first public release prefer BYOK (user's own key),
provider-approved commercial access, self-hosted open-weight inference,
or explicit provider agreements.

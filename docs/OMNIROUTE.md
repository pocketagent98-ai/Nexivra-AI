# OmniRoute integration

OmniRoute is the planned primary external model gateway for Nexivra AI
(cloud path):

```
DeerFlow harness -> UniversalModelGateway -> OmniRoute adapter -> provider
```

## Capabilities to use

- provider aggregation
- smart routing
- fallback
- health / cooldown handling
- quota awareness
- model profiles
- streaming
- tool calling
- optional fusion
- context/token optimization

## Rules

1. Do NOT stack FreeLLMAPI and OmniRoute as two independent smart
   routers. FreeLLMAPI stays an optional adapter/reference unless a clear
   documented technical reason appears.
2. Treat free-tier token totals as changing estimates, never permanent
   guarantees (see docs/PROVIDERS.md).
3. All app code still talks only to `UniversalModelGateway`; the
   OmniRoute adapter is just another adapter registered behind it.
4. OmniRoute is MIT-licensed third-party software; it is not affiliated
   with Nexivra AI and its license/attribution is preserved (see
   THIRD-PARTY-NOTICES.md).

## Current status

The gateway abstraction (`nexivra/gateway.py`) is implemented and tested;
the concrete OmniRoute adapter is roadmap work. The
`OpenAICompatibleAdapter` already covers the direct NVIDIA NIM and z.ai
paths used today.

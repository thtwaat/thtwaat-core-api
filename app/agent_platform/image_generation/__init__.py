"""Image Generation — reusable provider adapters + runtime around
``AgentRuntime``.

Prompt -> ImageGenerationProvider -> generated image bytes -> durable
storage (best-effort) + base64 in the response. AgentRuntime stays
modality-agnostic; everything provider-specific (SDK calls, size/quality
params) lives here.
"""

"""Voice AI — reusable STT/TTS adapters + runtime around ``AgentRuntime``.

Audio input -> STTProvider -> AgentRuntime.run_turn() -> TTSProvider -> audio
output. AgentRuntime stays modality-agnostic (text in, text out); everything
audio-specific (codecs, provider SDKs, duration accounting) lives here.
"""

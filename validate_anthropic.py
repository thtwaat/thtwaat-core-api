"""
validate_anthropic.py

End-to-end validation of the Anthropic (Claude) provider across both layers:
  Layer 1 — app/ai/providers/anthropic.py       (direct SDK)
  Layer 2 — app/agent_platform/providers/anthropic.py  (gateway wrapper)

Also validates OpenAI provider health and the Provider Registry.

Run:  python validate_anthropic.py
"""
import asyncio
import sys
import os
import io

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# ── helpers ──────────────────────────────────────────────────────────────────
PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

def ok(msg): print(f"  {PASS} {msg}")
def err(msg): print(f"  {FAIL} {msg}"); return False
def info(msg): print(f"  {INFO} {msg}")

# ─────────────────────────────────────────────────────────────────────────────
async def validate_env():
    print("\n── 1. Environment / .env ──────────────────────────────────────────")
    from app.config.settings import settings
    results = {}

    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        val = getattr(settings, key, None)
        if val:
            ok(f"{key} loaded  ({val[:12]}…)")
            results[key] = True
        else:
            err(f"{key} is MISSING from .env")
            results[key] = False

    return all(results.values())


async def validate_sdk():
    print("\n── 2. SDK Direct Test ─────────────────────────────────────────────")
    passed = True

    # Anthropic SDK
    try:
        from anthropic import AsyncAnthropic
        from app.config.settings import settings
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=64,
            messages=[{"role": "user", "content": "Say: SDK_OK"}],
        )
        content = resp.content[0].text
        if content and len(content) > 0:
            ok(f"Anthropic SDK direct call [OK]  → \"{content[:80]}\"")
        else:
            passed = err("Anthropic SDK returned empty content")
    except Exception as e:
        passed = err(f"Anthropic SDK error: {e}")

    # OpenAI SDK
    try:
        from openai import AsyncOpenAI
        from app.config.settings import settings
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say: SDK_OK"}],
            max_tokens=32,
        )
        content = resp.choices[0].message.content
        if content and len(content) > 0:
            ok(f"OpenAI SDK direct call [OK]  → \"{content[:80]}\"")
        else:
            passed = err("OpenAI SDK returned empty content")
    except Exception as e:
        passed = err(f"OpenAI SDK error: {e}")

    return passed


async def validate_registry():
    print("\n── 3. Provider Registry ───────────────────────────────────────────")
    # Trigger registration by importing provider modules
    import app.agent_platform.providers.openai    # noqa: F401
    import app.agent_platform.providers.anthropic  # noqa: F401
    import app.agent_platform.providers.gemini    # noqa: F401

    from app.agent_platform.registries.provider_registry import ProviderRegistry
    from app.config.settings import settings

    passed = True
    for name in ("openai", "anthropic", "gemini"):
        try:
            api_key = {
                "openai": settings.OPENAI_API_KEY,
                "anthropic": settings.ANTHROPIC_API_KEY,
                "gemini": settings.GEMINI_API_KEY,
            }[name]
            instance = ProviderRegistry.get_provider(name, api_key=api_key)
            ok(f"Provider '{name}' registered → {type(instance).__name__}")
        except Exception as e:
            passed = err(f"Provider '{name}' registration failed: {e}")

    return passed


async def validate_ai_layer():
    print("\n── 4. Layer 1 — app/ai Providers ─────────────────────────────────")
    from app.ai.providers.anthropic import AnthropicProvider as AIP
    from app.ai.providers.openai import OpenAIProvider as OIP
    passed = True

    TEST_MESSAGES = [{"role": "user", "content": "Reply with exactly: REAL_RESPONSE"}]

    # Anthropic
    try:
        p = AIP()
        resp = await p.chat(messages=TEST_MESSAGES, model="claude-haiku-4-5")
        if "mock" in resp.content.lower() or "stub" in resp.content.lower():
            passed = err(f"Anthropic (ai layer) returned mock/stub: {resp.content}")
        else:
            ok(f"Anthropic (ai layer) real response [OK]  model={resp.model_used}  tokens={resp.input_tokens}+{resp.output_tokens}")
            ok(f"  content → \"{resp.content[:100]}\"")
    except Exception as e:
        passed = err(f"Anthropic (ai layer) error: {e}")

    # OpenAI
    try:
        p = OIP()
        resp = await p.chat(messages=TEST_MESSAGES, model="gpt-4o-mini")
        if "mock" in resp.content.lower() or "stub" in resp.content.lower():
            passed = err(f"OpenAI (ai layer) returned mock/stub: {resp.content}")
        else:
            ok(f"OpenAI (ai layer) real response [OK]  model={resp.model_used}  tokens={resp.input_tokens}+{resp.output_tokens}")
            ok(f"  content → \"{resp.content[:100]}\"")
    except Exception as e:
        passed = err(f"OpenAI (ai layer) error: {e}")

    return passed


async def validate_gateway_layer():
    print("\n── 5. Layer 2 — AI Gateway (agent_platform) ──────────────────────")
    import app.agent_platform.providers.openai    # noqa: F401 — trigger registration
    import app.agent_platform.providers.anthropic  # noqa: F401

    from app.agent_platform.gateway.service import AIGatewayService
    from app.agent_platform.schemas import UnifiedChatRequest
    passed = True

    COMPANY = "test-company-001"
    TEST_MSGS = [{"role": "user", "content": "Reply with exactly: GATEWAY_OK"}]

    for provider, model in [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-haiku-4-5"),
    ]:
        req = UnifiedChatRequest(
            company_id=COMPANY,
            provider=provider,
            model=model,
            messages=TEST_MSGS,
            temperature=0.3,
            max_tokens=64,
        )
        try:
            resp = await AIGatewayService.process_request(req)
            if "mock" in resp.content.lower() or "mocked" in resp.content.lower():
                passed = err(f"Gateway [{provider}] still returning mock: {resp.content}")
            else:
                ok(
                    f"Gateway [{provider}] real response [OK]  "
                    f"model={resp.model}  tokens={resp.total_tokens}  "
                    f"latency={resp.latency:.2f}s"
                )
                ok(f"  content → \"{resp.content[:100]}\"")
        except Exception as e:
            passed = err(f"Gateway [{provider}] error: {e}")

    return passed


async def validate_agents():
    print("\n── 6. Create Test Agents (schema validation) ──────────────────────")
    from app.agent_platform.schemas import AgentCreate
    passed = True

    agents = [
        AgentCreate(
            name="OpenAI Test Agent",
            description="Validates OpenAI integration via the Agent Platform",
            system_prompt_template="You are a concise AI assistant. Keep all responses under 3 sentences.",
            temperature=0.5,
        ),
        AgentCreate(
            name="Claude Test Agent",
            description="Validates Anthropic Claude integration via the Agent Platform",
            system_prompt_template="You are a concise AI assistant. Keep all responses under 3 sentences.",
            temperature=0.5,
        ),
    ]

    for agent in agents:
        provider = "openai" if "OpenAI" in agent.name else "anthropic"
        ok(f"Agent schema valid: '{agent.name}' (provider={provider}, temp={agent.temperature})")

    return passed


async def validate_health():
    print("\n── 7. Provider Health Checks ──────────────────────────────────────")
    from app.ai.providers.factory import AIProviderFactory
    passed = True

    for provider_name in ("openai", "anthropic"):
        try:
            p = AIProviderFactory.get_provider(provider_name)
            healthy = await p.health()
            if healthy:
                ok(f"{provider_name}: healthy [OK]")
            else:
                passed = err(f"{provider_name}: health check returned False (key may be invalid)")
        except Exception as e:
            passed = err(f"{provider_name} health error: {e}")

    return passed


# ─────────────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 65)
    print(" ANTHROPIC + OPENAI PROVIDER VALIDATION")
    print("=" * 65)

    steps = [
        ("Environment",       validate_env),
        ("SDK Direct",        validate_sdk),
        ("Registry",          validate_registry),
        ("AI Layer",          validate_ai_layer),
        ("Gateway Layer",     validate_gateway_layer),
        ("Agent Schemas",     validate_agents),
        ("Health Checks",     validate_health),
    ]

    results = {}
    for name, fn in steps:
        try:
            results[name] = await fn()
        except Exception as ex:
            results[name] = err(f"Unexpected error in [{name}]: {ex}")

    print("\n" + "=" * 65)
    print(" SUMMARY")
    print("=" * 65)
    all_passed = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {name}")
        if not passed:
            all_passed = False

    print("=" * 65)
    if all_passed:
        print("  ALL CHECKS PASSED — Anthropic provider is fully live.")
    else:
        print("\033[91m  SOME CHECKS FAILED — review output above.\033[0m")
        sys.exit(1)
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(main())

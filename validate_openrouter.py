"""
validate_openrouter.py

End-to-end validation of the OpenRouter provider across both layers:
  Layer 1 -- app/ai/providers/openrouter.py              (direct SDK)
  Layer 2 -- app/agent_platform/providers/openrouter.py  (gateway wrapper)

Run:  python -X utf8 validate_openrouter.py
"""
import asyncio
import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 on Windows console
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

def ok(msg):  print(f"  {PASS} {msg}")
def err(msg): print(f"  {FAIL} {msg}"); return False
def info(msg):print(f"  {INFO} {msg}")


# ── Step 1: Environment ───────────────────────────────────────────────────────
async def validate_env():
    print("\n-- 1. Environment / .env ------------------------------------------")
    from app.config.settings import settings

    key = settings.OPENROUTER_API_KEY
    if key:
        ok(f"OPENROUTER_API_KEY loaded  ({key[:16]}...)")
        return True
    else:
        return err("OPENROUTER_API_KEY is MISSING or empty in .env")


# ── Step 2: SDK direct (httpx health + openai SDK call) ───────────────────────
async def validate_sdk():
    print("\n-- 2. SDK Direct Test (httpx + openai SDK) ------------------------")
    from app.config.settings import settings
    passed = True

    # 2a. Verify the /models endpoint is reachable with this key
    try:
        import httpx
        async with httpx.AsyncClient() as http:
            r = await http.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                timeout=10,
            )
            if r.status_code == 200:
                model_count = len(r.json().get("data", []))
                ok(f"OpenRouter /models endpoint reachable -- {model_count} models available")
            else:
                passed = err(f"OpenRouter /models returned HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        passed = err(f"OpenRouter /models error: {e}")

    # 2b. Real chat completion via openai SDK pointed at OpenRouter
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://thtwaat.com",
                "X-Title": "THTWAAT Core API",
            },
        )
        resp = await client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct:free",
            messages=[{"role": "user", "content": "Reply with exactly: SDK_OK"}],
            max_tokens=32,
        )
        content = resp.choices[0].message.content or ""
        if content:
            ok(f"OpenRouter SDK chat call [OK] -- \"{content[:100]}\"")
        else:
            passed = err("OpenRouter SDK returned empty content")
    except Exception as e:
        passed = err(f"OpenRouter SDK chat error: {e}")

    return passed


# ── Step 3: Provider Registry ─────────────────────────────────────────────────
async def validate_registry():
    print("\n-- 3. Provider Registry -------------------------------------------")
    import app.agent_platform.providers.openrouter  # noqa: F401 -- trigger registration

    from app.agent_platform.registries.provider_registry import ProviderRegistry
    from app.config.settings import settings

    try:
        instance = ProviderRegistry.get_provider(
            "openrouter", api_key=settings.OPENROUTER_API_KEY
        )
        ok(f"Provider 'openrouter' registered -> {type(instance).__name__}")
        return True
    except Exception as e:
        return err(f"Provider 'openrouter' registration failed: {e}")


# ── Step 4: Layer 1 -- app/ai ─────────────────────────────────────────────────
async def validate_ai_layer():
    print("\n-- 4. Layer 1 -- app/ai/providers/openrouter.py ------------------")
    from app.ai.providers.openrouter import OpenRouterProvider

    passed = True
    p = OpenRouterProvider()

    # Health check
    try:
        healthy = await p.health()
        if healthy:
            ok("health() -> True (key accepted)")
        else:
            passed = err("health() -> False (key rejected or unreachable)")
    except Exception as e:
        passed = err(f"health() error: {e}")

    # Models list
    try:
        models = await p.models()
        ok(f"models() -> {len(models)} model(s) returned  first={models[0]}")
    except Exception as e:
        passed = err(f"models() error: {e}")

    # Real chat call
    TEST_MESSAGES = [{"role": "user", "content": "Reply with exactly: REAL_RESPONSE"}]
    try:
        resp = await p.chat(
            messages=TEST_MESSAGES,
            model="meta-llama/llama-3.1-8b-instruct:free",
        )
        if "mock" in resp.content.lower() or "stub" in resp.content.lower():
            passed = err(f"ai layer returned mock/stub: {resp.content}")
        else:
            ok(
                f"chat() real response [OK] "
                f"model={resp.model_used} "
                f"tokens={resp.input_tokens}+{resp.output_tokens}"
            )
            ok(f"  content -> \"{resp.content[:120]}\"")
    except Exception as e:
        passed = err(f"chat() error: {e}")

    return passed


# ── Step 5: Layer 2 -- AI Gateway ─────────────────────────────────────────────
async def validate_gateway_layer():
    print("\n-- 5. Layer 2 -- AI Gateway (agent_platform) ---------------------")
    import app.agent_platform.providers.openrouter  # noqa: F401

    from app.agent_platform.gateway.service import AIGatewayService
    from app.agent_platform.schemas import UnifiedChatRequest
    passed = True

    req = UnifiedChatRequest(
        company_id="test-company-openrouter",
        provider="openrouter",
        model="meta-llama/llama-3.1-8b-instruct:free",
        messages=[{"role": "user", "content": "Reply with exactly: GATEWAY_OK"}],
        temperature=0.3,
        max_tokens=64,
    )

    try:
        resp = await AIGatewayService.process_request(req)
        if "mocked" in resp.content.lower() or "mock" in resp.content.lower():
            passed = err(f"Gateway still returning mock: {resp.content}")
        else:
            ok(
                f"Gateway [openrouter] real response [OK] "
                f"model={resp.model} "
                f"tokens={resp.total_tokens} "
                f"latency={resp.latency:.2f}s"
            )
            ok(f"  content -> \"{resp.content[:120]}\"")
    except Exception as e:
        passed = err(f"Gateway [openrouter] error: {e}")

    return passed


# ── Step 6: Create test agent ─────────────────────────────────────────────────
async def validate_agent():
    print("\n-- 6. Create OpenRouter Test Agent (schema validation) -----------")
    from app.agent_platform.schemas import AgentCreate

    agent = AgentCreate(
        name="OpenRouter Test Agent",
        description="Validates OpenRouter integration via the Agent Platform gateway",
        system_prompt_template=(
            "You are a concise AI assistant powered by OpenRouter. "
            "Keep all responses under 3 sentences."
        ),
        temperature=0.5,
    )
    ok(f"Agent schema valid: '{agent.name}' (provider=openrouter, temp={agent.temperature})")
    return True


# ── Step 7: Fallback model chain ──────────────────────────────────────────────
async def validate_fallback():
    print("\n-- 7. Fallback Model Chain ----------------------------------------")
    from app.ai.providers.openrouter import OPENROUTER_FALLBACK_MODELS, OpenRouterProvider

    info(f"Fallback chain: {OPENROUTER_FALLBACK_MODELS}")

    p = OpenRouterProvider()
    # Test the first fallback model directly
    fallback = OPENROUTER_FALLBACK_MODELS[0]
    try:
        resp = await p.chat(
            messages=[{"role": "user", "content": "Say: FALLBACK_OK"}],
            model=fallback,
            max_tokens=32,
        )
        ok(f"Fallback model '{fallback}' responded [OK] -> \"{resp.content[:80]}\"")
        return True
    except Exception as e:
        return err(f"Fallback model '{fallback}' failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 65)
    print(" OPENROUTER PROVIDER VALIDATION")
    print("=" * 65)

    steps = [
        ("Environment",       validate_env),
        ("SDK Direct",        validate_sdk),
        ("Registry",          validate_registry),
        ("AI Layer",          validate_ai_layer),
        ("Gateway Layer",     validate_gateway_layer),
        ("Agent Schema",      validate_agent),
        ("Fallback Chain",    validate_fallback),
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
        print("  ALL CHECKS PASSED -- OpenRouter provider is fully live.")
    else:
        print("  SOME CHECKS FAILED -- review output above.")
        sys.exit(1)
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())

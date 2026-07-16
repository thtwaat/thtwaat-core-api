import pytest
from app.agent_platform.schemas import UnifiedChatRequest
from app.agent_platform.gateway.service import AIGatewayService
import app.agent_platform.providers.openai
import app.agent_platform.providers.gemini
import app.agent_platform.providers.anthropic
import app.agent_platform.providers.openrouter
import app.agent_platform.providers.ollama

@pytest.mark.asyncio
async def test_gateway_routing():
    """Test that the gateway can route to OpenAI provider correctly and return unified response."""
    request = UnifiedChatRequest(
        company_id="test_company",
        provider="openai",
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}]
    )
    
    response = await AIGatewayService.process_request(request)
    
    assert response.provider == "openai"
    assert response.model == "gpt-4o"
    assert response.content == "This is a mocked response from OpenAI."
    assert response.input_tokens > 0

@pytest.mark.asyncio
async def test_gateway_gemini_routing():
    """Test routing to Gemini provider."""
    request = UnifiedChatRequest(
        company_id="test_company",
        provider="gemini",
        model="gemini-1.5-pro",
        messages=[{"role": "user", "content": "Hello"}]
    )
    
    response = await AIGatewayService.process_request(request)
    
    assert response.provider == "gemini"
    assert response.model == "gemini-1.5-pro"
    assert response.content == "This is a mocked response from Gemini."

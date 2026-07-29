from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry

import httpx

class OllamaProvider(LLMProvider):
    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        # Default to a lightweight model if not provided
        model_name = request.model or "qwen2.5-coder:3b"
        
        # Ollama usually runs on the host machine. From docker, use host.docker.internal
        # If running outside docker, it's localhost. Let's try host.docker.internal first.
        # But wait, we can just use an environment variable or default to host.docker.internal
        import os
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        
        payload = {
            "model": model_name,
            "messages": request.messages,
            "stream": False,
            "options": {
                "temperature": request.temperature or 0.7,
            }
        }
        
        input_tokens = 0
        output_tokens = 0
        content = ""
        finish_reason = "stop"
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{ollama_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                
                content = data.get("message", {}).get("content", "")
                input_tokens = data.get("prompt_eval_count", 0)
                output_tokens = data.get("eval_count", 0)
                if data.get("done_reason"):
                    finish_reason = data["done_reason"]
                    
        except Exception as e:
            content = f"Ollama Provider Error: {str(e)}"
            finish_reason = "error"

        return UnifiedChatResponse(
            content=content,
            provider="ollama",
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason=finish_reason
        )

ProviderRegistry.register("ollama", OllamaProvider)

import warnings
# TODO: Migrate to `google-genai` once added to requirements.txt.
# The `google-generativeai` package still works but is deprecated.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry


class GeminiProvider(LLMProvider):
    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        """Call Google Gemini API via the google-generativeai SDK."""
        genai.configure(api_key=self.api_key)

        # Normalize model name: strip 'models/' prefix if present (SDK adds it internally)
        model_name = (request.model or "gemini-2.0-flash").replace("models/", "")
        model = genai.GenerativeModel(model_name=model_name)

        # Convert unified message format to Gemini history format
        # Gemini expects: [{"role": "user"|"model", "parts": [...]}]
        history = []
        user_message = ""
        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Gemini uses "model" for assistant messages
            gemini_role = "model" if role == "assistant" else "user"
            if history and history[-1]["role"] == gemini_role:
                # Merge consecutive same-role messages
                history[-1]["parts"].append(content)
            else:
                history.append({"role": gemini_role, "parts": [content]})

        # The last message must be a user message; extract it for send_message
        if history and history[-1]["role"] == "user":
            user_parts = history[-1]["parts"]
            user_message = " ".join(str(p) for p in user_parts)
            history = history[:-1]  # Remove last entry — it becomes the prompt
        elif history:
            user_message = ""  # Fallback: shouldn't happen in normal flow

        chat = model.start_chat(history=history)

        generation_config = genai.GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )

        input_tokens = 0
        output_tokens = 0
        finish_reason = None
        
        try:
            response = chat.send_message(
                user_message,
                generation_config=generation_config,
            )
            content = response.text or ""
            
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                
            if response.candidates:
                finish_reason = str(response.candidates[0].finish_reason.name).lower()

        except Exception as e:
            # Production-ready: Handle upstream provider errors gracefully
            content = f"Google Gemini API Error: {str(e)}"
            finish_reason = "error"

        return UnifiedChatResponse(
            content=content,
            provider="gemini",
            model=request.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason=finish_reason,
        )


ProviderRegistry.register("gemini", GeminiProvider)

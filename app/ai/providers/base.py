"""
app/ai/providers/base.py

Adapter pattern interface for all AI Providers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class AIProviderResponse:
    def __init__(
        self,
        content: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model_used: str = "",
        provider_response_id: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model_used = model_used
        self.provider_response_id = provider_response_id
        self.metadata = metadata or {}


class AIProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        """Process multi-turn chat."""
        pass

    @abstractmethod
    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        """Process single prompt generation."""
        pass

    @abstractmethod
    async def models(self) -> List[str]:
        """List supported models."""
        pass

    @abstractmethod
    async def health(self) -> bool:
        """Check provider health/configuration."""
        pass

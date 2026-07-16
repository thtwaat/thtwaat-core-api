from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse

class LLMProvider(ABC):
    """
    Abstract Base Class for all AI Providers.
    All providers must implement this interface to ensure
    no provider-specific logic leaks into the core engine.
    """
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def generate_response(
        self,
        request: UnifiedChatRequest
    ) -> UnifiedChatResponse:
        """
        Executes the LLM call using the unified request format.
        
        Args:
            request: UnifiedChatRequest object
            
        Returns:
            UnifiedChatResponse object containing the content and usage metrics.
        """
        pass

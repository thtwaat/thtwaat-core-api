from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseTool(ABC):
    """
    Abstract Base Class for all Pluggable Tools.
    """
    
    # Must be overridden by subclasses
    name: str = ""
    description: str = ""
    
    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """
        JSON Schema defining the tool's input parameters.
        This schema is exposed to the LLM.
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Executes the tool's core logic with the LLM-provided arguments.
        
        Args:
            **kwargs: Arguments extracted by the LLM based on the schema.
            
        Returns:
            The result of the tool execution, typically a string or dict
            that will be fed back into the LLM context.
        """
        pass

from typing import Dict, Type, List
from app.agent_platform.tools.base import BaseTool

class ToolRegistry:
    """
    Registry for loading and instantiating Pluggable Tools.
    """
    
    _tools: Dict[str, Type[BaseTool]] = {}

    @classmethod
    def register(cls, tool_class: Type[BaseTool]):
        """Registers a tool class."""
        if not tool_class.name:
            raise ValueError("Tool must define a 'name' attribute.")
        cls._tools[tool_class.name] = tool_class

    @classmethod
    def get_tool(cls, name: str) -> BaseTool:
        """Instantiates a tool by name."""
        tool_class = cls._tools.get(name)
        if not tool_class:
            raise ValueError(f"Tool '{name}' is not registered.")
        return tool_class()

    @classmethod
    def list_tools(cls) -> List[str]:
        """Names of every registered tool, sorted for stable listing output."""
        return sorted(cls._tools.keys())

    @classmethod
    def get_schemas_for_tools(cls, tool_names: List[str]) -> List[Dict]:
        """Gets schemas for a list of tool names to pass to LLM."""
        schemas = []
        for name in tool_names:
            tool = cls.get_tool(name)
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.schema
            })
        return schemas

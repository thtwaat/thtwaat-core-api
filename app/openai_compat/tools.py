"""Function / tool-calling abstraction (OpenAI tools shape)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def normalize_tools(tools: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Normalize provider-agnostic tool defs into OpenAI function-tools."""
    if not tools:
        return []
    out: List[Dict[str, Any]] = []
    for raw in tools:
        if not isinstance(raw, dict):
            continue
        if raw.get("type") == "function" and isinstance(raw.get("function"), dict):
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": str(raw["function"].get("name") or ""),
                        "description": raw["function"].get("description"),
                        "parameters": raw["function"].get("parameters") or {"type": "object", "properties": {}},
                    },
                }
            )
            continue
        # Shorthand: {name, description, parameters}
        name = raw.get("name")
        if name:
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": str(name),
                        "description": raw.get("description"),
                        "parameters": raw.get("parameters") or {"type": "object", "properties": {}},
                    },
                }
            )
    return [t for t in out if t["function"]["name"]]


def normalize_tool_choice(tool_choice: Any) -> Any:
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        return tool_choice
    if isinstance(tool_choice, dict):
        return tool_choice
    return "auto"

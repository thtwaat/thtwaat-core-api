"""Knowledge-search tool — lets the model decide when to query the agent's knowledge bases.

Reference implementation of the BaseTool/ToolRegistry interface (see app/agent_platform/tools/base.py).
Wraps the same KnowledgeService used by the always-on RAG pre-retrieval step, so it reuses the
existing pgvector search rather than duplicating it.
"""
from typing import Any, Dict

from app.agent_platform.registries.tool_registry import ToolRegistry
from app.agent_platform.tools.base import BaseTool


class KnowledgeSearchTool(BaseTool):
    name = "knowledge_search"
    description = (
        "Search this agent's attached knowledge bases for information relevant to the user's "
        "question. Use this when you need facts, policies, or documentation you don't already "
        "have in the conversation."
    )

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query — what to look up in the knowledge base.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, **kwargs) -> str:
        db = kwargs.get("db")
        company_id = kwargs.get("company_id")
        agent_id = kwargs.get("agent_id")
        if db is None or company_id is None or agent_id is None:
            return "Knowledge search is unavailable in this context."

        from app.agent_platform.agent_runtime import search_agent_knowledge

        results = search_agent_knowledge(db, agent_id, query, company_id, top_k=5)
        if not results:
            return "No relevant knowledge found."

        blocks = [f"[{i}] (Source: {r.document_name})\n{r.text}" for i, r in enumerate(results, start=1)]
        return "\n\n---\n\n".join(blocks)


ToolRegistry.register(KnowledgeSearchTool)

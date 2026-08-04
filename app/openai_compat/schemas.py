"""OpenAI-compatible wire schemas for /v1/chat/completions (Day 1)."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "function"]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)
    messages: List[ChatMessage] = Field(..., min_length=1)
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=128000)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    n: Optional[int] = Field(default=1, ge=1, le=1)
    stream: bool = False
    stop: Optional[Union[str, List[str]]] = None
    user: Optional[str] = None
    # Tool calling (OpenAI-compatible, additive)
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    # THTWAAT extension: force provider when using gateway mode
    provider: Optional[str] = Field(
        default=None,
        description=(
            "Optional THTWAAT extension — auto|ollama|openai|gemini|anthropic|openrouter. "
            "Default auto. On stream failures before the first token, "
            "STREAM_FALLBACK_ORDER providers are tried."
        ),
    )
    # Additive enterprise extensions (ignored by pure OpenAI clients)
    conversation_id: Optional[str] = Field(
        default=None, description="THTWAAT: attach conversation memory when available"
    )
    rag_query: Optional[str] = Field(
        default=None, description="THTWAAT: optional RAG query to prepend knowledge context"
    )
    knowledge_base_id: Optional[str] = None
    stream_options: Optional[Dict[str, Any]] = None



class CompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Optional[str] = "stop"
    logprobs: Optional[Any] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: CompletionUsage
    system_fingerprint: Optional[str] = None


class ChatCompletionChunkDelta(BaseModel):
    role: Optional[Literal["assistant"]] = None
    content: Optional[str] = None


class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None
    logprobs: Optional[Any] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]
    system_fingerprint: Optional[str] = None
    # OpenAI optionally includes usage on the final chunk when stream_options.include_usage
    usage: Optional[CompletionUsage] = None


class ModelObject(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class ModelsListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: List[ModelObject]

"""
app/agent_platform/knowledge/embeddings.py
Embedding service for the RAG pipeline.

Strategy (provider-independent):
  PRIMARY:  Ollama  nomic-embed-text  → 768-dim vectors
  FALLBACK: Gemini  text-embedding-004 → 768-dim vectors

The fallback kicks in automatically when Ollama is unreachable.
Both providers are tried in order; if both fail an exception is raised.
"""
import logging
from typing import List, Optional

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
OLLAMA_EMBED_MODEL = "nomic-embed-text"
GEMINI_EMBED_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSIONS = 768

# Timeout for Ollama (local, should be fast)
_OLLAMA_TIMEOUT = 30.0


class EmbeddingService:
    """
    Generates text embeddings using Ollama (primary) or Gemini (fallback).

    All methods return plain Python lists of floats so callers don't need
    to import any provider SDK.
    """

    # ── Public API ────────────────────────────────────────────────────────────

    @classmethod
    async def embed_text(cls, text: str) -> List[float]:
        """
        Embed a single string.  Returns a 768-dim float list.

        Tries Ollama first; falls back to Gemini on any failure.
        """
        # Truncate very long texts to avoid provider limits
        text = text[:8000]

        # PRIMARY: Ollama
        vector = await cls._try_ollama([text])
        if vector is not None:
            return vector[0]

        # FALLBACK: Gemini
        logger.warning("[Embeddings] Ollama unavailable, falling back to Gemini")
        vector = await cls._try_gemini([text])
        if vector is not None:
            return vector[0]

        raise RuntimeError(
            "Embedding generation failed: both Ollama and Gemini are unavailable."
        )

    @classmethod
    async def embed_batch(cls, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of strings.  Returns a list of 768-dim float lists.

        Tries Ollama first (sequential, as Ollama doesn't support batch API).
        Falls back to Gemini batch API on failure.
        """
        if not texts:
            return []

        # Truncate
        texts = [t[:8000] for t in texts]

        # PRIMARY: Ollama (sequential)
        vectors = await cls._try_ollama(texts)
        if vectors is not None:
            return vectors

        # FALLBACK: Gemini
        logger.warning(
            "[Embeddings] Ollama unavailable for batch, falling back to Gemini"
        )
        vectors = await cls._try_gemini(texts)
        if vectors is not None:
            return vectors

        raise RuntimeError(
            "Batch embedding failed: both Ollama and Gemini are unavailable."
        )

    # ── Providers ─────────────────────────────────────────────────────────────

    @classmethod
    async def _try_ollama(cls, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Call the Ollama /api/embed endpoint.
        Returns None (not an exception) if Ollama is unreachable.
        """
        ollama_url = settings.OLLAMA_URL or "http://localhost:11434"
        embed_url = f"{ollama_url}/api/embed"

        results: List[List[float]] = []
        try:
            async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
                for text in texts:
                    resp = await client.post(
                        embed_url,
                        json={"model": OLLAMA_EMBED_MODEL, "input": text},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    # Ollama returns {"embeddings": [[...float...]]}
                    embedding = data.get("embeddings", [[]])[0]
                    if not embedding:
                        raise ValueError("Ollama returned empty embedding")
                    results.append(embedding)

            logger.debug(
                f"[Embeddings] Ollama embedded {len(texts)} text(s) "
                f"→ dim={len(results[0]) if results else 'n/a'}"
            )
            return results

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"[Embeddings] Ollama connection failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"[Embeddings] Ollama embed error: {e}")
            return None

    @classmethod
    async def _try_gemini(cls, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Call the Gemini text-embedding-004 API.
        Returns None if no API key is configured or the call fails.
        """
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logger.warning("[Embeddings] GEMINI_API_KEY not set, cannot use Gemini fallback")
            return None

        try:
            import google.generativeai as genai  # already in requirements.txt

            genai.configure(api_key=api_key)

            results: List[List[float]] = []
            for text in texts:
                result = genai.embed_content(
                    model=GEMINI_EMBED_MODEL,
                    content=text,
                    task_type="retrieval_document",
                )
                embedding = result["embedding"]
                results.append(embedding)

            logger.debug(
                f"[Embeddings] Gemini embedded {len(texts)} text(s) "
                f"→ dim={len(results[0]) if results else 'n/a'}"
            )
            return results

        except Exception as e:
            logger.error(f"[Embeddings] Gemini embed error: {e}")
            return None

    @classmethod
    def get_model_name(cls) -> str:
        """Returns the active embedding model name for metadata storage."""
        # We optimistically return Ollama; the actual call resolves at runtime.
        return OLLAMA_EMBED_MODEL

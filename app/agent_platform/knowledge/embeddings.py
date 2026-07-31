"""
app/agent_platform/knowledge/embeddings.py
Embedding service for the RAG pipeline.

Strategy (provider-independent):
  PRIMARY:  Ollama  (settings.EMBEDDING_OLLAMA_MODEL) → 768-dim vectors
  FALLBACK: Gemini  (settings.EMBEDDING_GEMINI_MODEL) → 768-dim vectors

The fallback kicks in automatically when Ollama is unreachable.
Both providers are tried in order; if both fail an exception is raised.

Every vector is validated against settings.EMBEDDING_DIMENSIONS before it is
returned, because the `chunks.embedding` column is a fixed-width pgvector(768):
a wrong-sized vector would either fail the insert or silently corrupt search.
"""
import asyncio
import logging
import math
from typing import List, Optional

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
OLLAMA_EMBED_MODEL = settings.EMBEDDING_OLLAMA_MODEL
GEMINI_EMBED_MODEL = settings.EMBEDDING_GEMINI_MODEL
EMBEDDING_DIMENSIONS = settings.EMBEDDING_DIMENSIONS

# Timeout for Ollama (local, should be fast)
_OLLAMA_TIMEOUT = 30.0
# Pulling an embedding model on first use can take a few minutes.
_OLLAMA_PULL_TIMEOUT = 900.0

# Pull the missing model at most once per process. Not a lock: search runs on
# short-lived event loops, and a duplicate /api/pull is deduplicated by Ollama.
_pull_attempted: set[str] = set()


def _normalize(vector: List[float]) -> List[float]:
    """Scale to unit length so cosine distance is comparable across providers."""
    norm = math.sqrt(sum(v * v for v in vector))
    if not norm:
        return vector
    return [v / norm for v in vector]


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
        return (await cls.embed_batch([text]))[0]

    @classmethod
    async def embed_batch(cls, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of strings.  Returns a list of 768-dim float lists.

        Tries Ollama first (sequential, as Ollama doesn't support batch API).
        Falls back to Gemini batch API on failure.
        """
        if not texts:
            return []

        # Truncate very long texts to avoid provider limits
        texts = [t[:8000] for t in texts]

        failures: List[str] = []

        # PRIMARY: Ollama
        vectors, error = await cls._try_ollama(texts)
        if vectors is not None:
            return vectors
        failures.append(f"ollama: {error}")

        # FALLBACK: Gemini
        logger.warning("[Embeddings] Ollama unavailable (%s), falling back to Gemini", error)
        vectors, error = await cls._try_gemini(texts)
        if vectors is not None:
            return vectors
        failures.append(f"gemini: {error}")

        raise RuntimeError(
            "Embedding generation failed; no provider available — " + "; ".join(failures)
        )

    @classmethod
    async def health(cls) -> dict:
        """Report which embedding providers can currently serve requests."""
        ollama_vectors, ollama_error = await cls._try_ollama(["healthcheck"])
        result = {
            "dimensions": EMBEDDING_DIMENSIONS,
            "ollama": {
                "model": OLLAMA_EMBED_MODEL,
                "url": settings.OLLAMA_URL,
                "ok": ollama_vectors is not None,
                "error": ollama_error,
            },
        }
        if ollama_vectors is None:
            gemini_vectors, gemini_error = await cls._try_gemini(["healthcheck"])
            result["gemini"] = {
                "model": GEMINI_EMBED_MODEL,
                "ok": gemini_vectors is not None,
                "error": gemini_error,
            }
        result["ok"] = result["ollama"]["ok"] or result.get("gemini", {}).get("ok", False)
        return result

    # ── Providers ─────────────────────────────────────────────────────────────

    @classmethod
    def _validate(cls, provider: str, vectors: List[List[float]]) -> Optional[str]:
        for vector in vectors:
            if not vector:
                return f"{provider} returned an empty embedding"
            if len(vector) != EMBEDDING_DIMENSIONS:
                return (
                    f"{provider} returned {len(vector)} dimensions, "
                    f"expected {EMBEDDING_DIMENSIONS} — check the configured model"
                )
        return None

    @classmethod
    async def _ensure_ollama_model(cls, client: httpx.AsyncClient, base_url: str) -> None:
        """Pull the embedding model once if the server does not have it yet."""
        if not settings.EMBEDDING_OLLAMA_AUTO_PULL:
            return
        if OLLAMA_EMBED_MODEL in _pull_attempted:
            return
        _pull_attempted.add(OLLAMA_EMBED_MODEL)
        logger.warning(
            "[Embeddings] Ollama model %s missing — pulling it now (one-time)",
            OLLAMA_EMBED_MODEL,
        )
        resp = await client.post(
            f"{base_url}/api/pull",
            json={"model": OLLAMA_EMBED_MODEL, "stream": False},
            timeout=_OLLAMA_PULL_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("[Embeddings] Ollama model %s pulled", OLLAMA_EMBED_MODEL)

    @classmethod
    async def _embed_with_ollama(
        cls, client: httpx.AsyncClient, base_url: str, texts: List[str]
    ) -> List[List[float]]:
        results: List[List[float]] = []
        for text in texts:
            resp = await client.post(
                f"{base_url}/api/embed",
                json={"model": OLLAMA_EMBED_MODEL, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            # Ollama returns {"embeddings": [[...float...]]}
            embedding = (data.get("embeddings") or [[]])[0]
            results.append(_normalize(embedding) if embedding else [])
        return results

    @classmethod
    async def _try_ollama(
        cls, texts: List[str]
    ) -> tuple[Optional[List[List[float]]], Optional[str]]:
        """
        Call the Ollama /api/embed endpoint.
        Returns (vectors, None) on success or (None, reason) on failure — never raises.
        """
        base_url = (settings.OLLAMA_URL or "http://localhost:11434").rstrip("/")

        try:
            async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
                try:
                    results = await cls._embed_with_ollama(client, base_url, texts)
                except httpx.HTTPStatusError as exc:
                    # Ollama answers 404 when the model has never been pulled.
                    if exc.response.status_code != 404:
                        raise
                    await cls._ensure_ollama_model(client, base_url)
                    results = await cls._embed_with_ollama(client, base_url, texts)

            problem = cls._validate("Ollama", results)
            if problem:
                logger.warning("[Embeddings] %s", problem)
                return None, problem

            logger.debug(
                "[Embeddings] Ollama embedded %d text(s) → dim=%d",
                len(texts),
                len(results[0]),
            )
            return results, None

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return None, f"connection failed ({e})"
        except Exception as e:
            return None, str(e)

    @classmethod
    async def _try_gemini(
        cls, texts: List[str]
    ) -> tuple[Optional[List[List[float]]], Optional[str]]:
        """
        Call the Gemini embedding API.
        Returns (vectors, None) on success or (None, reason) on failure — never raises.
        """
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return None, "GEMINI_API_KEY not set"

        def _run() -> List[List[float]]:
            import google.generativeai as genai  # already in requirements.txt

            genai.configure(api_key=api_key)
            vectors: List[List[float]] = []
            for text in texts:
                result = genai.embed_content(
                    model=GEMINI_EMBED_MODEL,
                    content=text,
                    task_type="retrieval_document",
                    # gemini-embedding-001 defaults to 3072 dims; the pgvector
                    # column is fixed at EMBEDDING_DIMENSIONS. Truncated outputs
                    # are not unit-normalized, hence _normalize below.
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                )
                vectors.append(_normalize(result["embedding"]))
            return vectors

        try:
            # The SDK is synchronous; keep the event loop free.
            results = await asyncio.to_thread(_run)
        except Exception as e:
            logger.error("[Embeddings] Gemini embed error: %s", e)
            return None, str(e)

        problem = cls._validate("Gemini", results)
        if problem:
            logger.warning("[Embeddings] %s", problem)
            return None, problem

        logger.debug(
            "[Embeddings] Gemini embedded %d text(s) → dim=%d", len(texts), len(results[0])
        )
        return results, None

    @classmethod
    def get_model_name(cls) -> str:
        """Returns the active embedding model name for metadata storage."""
        # We optimistically return Ollama; the actual call resolves at runtime.
        return OLLAMA_EMBED_MODEL

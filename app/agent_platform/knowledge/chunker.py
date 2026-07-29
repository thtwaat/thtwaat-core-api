"""
app/agent_platform/knowledge/chunker.py
Recursive character-based text chunker.

Splits text into overlapping windows of `chunk_size` characters,
respecting natural paragraph/sentence boundaries by trying a
priority list of separators before falling back to hard cuts.

Usage:
    from app.agent_platform.knowledge.chunker import TextChunker, ChunkResult

    chunks = TextChunker().split(text, metadata={"page": 1})
    # → List[ChunkResult]
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any

# Default tuning constants
_DEFAULT_CHUNK_SIZE = 800    # target characters per chunk
_DEFAULT_OVERLAP    = 100    # overlap between consecutive chunks

# Separators tried in order (most preferred → least preferred)
_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]


@dataclass
class ChunkResult:
    """A single text chunk ready for embedding."""
    chunk_index: int
    text_content: str
    metadata_json: Dict[str, Any] = field(default_factory=dict)


class TextChunker:
    """
    Recursive character text splitter.

    Algorithm:
      1. Try to split on the highest-priority separator that exists in the text.
      2. Merge resulting splits back into windows of <= chunk_size chars,
         carrying `overlap` chars from the previous window.
    """

    def __init__(
        self,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_OVERLAP,
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    # ── Public API ────────────────────────────────────────────────────────────

    def split(
        self,
        text: str,
        metadata: Dict[str, Any] | None = None,
        start_index: int = 0,
    ) -> List[ChunkResult]:
        """
        Split *text* into overlapping chunks.

        Args:
            text:        The raw text to split.
            metadata:    Base metadata to attach to every chunk (e.g., {"page": 3}).
            start_index: chunk_index offset (when chunking multi-page docs).

        Returns:
            Ordered list of ChunkResult objects.
        """
        metadata = metadata or {}
        raw_chunks = self._split_text(text)
        results: List[ChunkResult] = []
        for i, chunk_text in enumerate(raw_chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
            results.append(
                ChunkResult(
                    chunk_index=start_index + i,
                    text_content=chunk_text,
                    metadata_json={**metadata, "char_count": len(chunk_text)},
                )
            )
        return results

    def split_pages(
        self,
        pages: List[Dict[str, Any]],
    ) -> List[ChunkResult]:
        """
        Convenience method to chunk a list of page dicts produced by extractors.

        Args:
            pages: List of dicts with at least {'text': str, 'metadata': dict}.
                   Typically the .pages attribute of an ExtractionResult.

        Returns:
            Flat ordered list of ChunkResult, chunk_index is global across pages.
        """
        all_chunks: List[ChunkResult] = []
        global_idx = 0
        for page in pages:
            text = page["text"] if isinstance(page, dict) else page.text
            meta = page["metadata"] if isinstance(page, dict) else page.metadata
            page_chunks = self.split(text, metadata=meta, start_index=global_idx)
            all_chunks.extend(page_chunks)
            global_idx += len(page_chunks)
        return all_chunks

    # ── Internal ──────────────────────────────────────────────────────────────

    def _split_text(self, text: str) -> List[str]:
        """Core recursive split returning a list of chunk strings."""
        if len(text) <= self.chunk_size:
            return [text]

        # Find a separator that exists in the text
        separator = ""
        for sep in _SEPARATORS:
            if sep and sep in text:
                separator = sep
                break

        if separator:
            splits = text.split(separator)
        else:
            # Hard cut if no separator found
            splits = [
                text[i : i + self.chunk_size]
                for i in range(0, len(text), self.chunk_size)
            ]

        return self._merge_splits(splits, separator)

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """
        Merge short splits into chunks of <= chunk_size chars,
        with overlap carried from the previous chunk.
        """
        chunks: List[str] = []
        current_parts: List[str] = []
        current_len = 0

        for part in splits:
            part_len = len(part) + len(separator)

            if current_len + part_len > self.chunk_size and current_parts:
                # Flush current window
                chunks.append(separator.join(current_parts))

                # Keep overlap: drop from the front until we're within overlap budget
                while current_parts and (
                    current_len - len(current_parts[0]) - len(separator)
                    > self.overlap
                ):
                    removed = current_parts.pop(0)
                    current_len -= len(removed) + len(separator)

            current_parts.append(part)
            current_len += part_len

        if current_parts:
            chunks.append(separator.join(current_parts))

        return chunks

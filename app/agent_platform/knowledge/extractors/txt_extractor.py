"""
app/agent_platform/knowledge/extractors/txt_extractor.py
Plain-text and Markdown extraction.

Reads the file as UTF-8 (with latin-1 fallback).
Splits on double-newlines to create natural paragraph blocks,
each becoming a PageBlock for consistency with other extractors.
"""
import logging
from typing import List

from .base import BaseExtractor, ExtractionResult, PageBlock

logger = logging.getLogger(__name__)

# Maximum characters per PageBlock — avoids single monster blocks
_MAX_BLOCK_CHARS = 3000


class TXTExtractor(BaseExtractor):
    """Extract text from plain .txt and .md files."""

    def extract(self, file_path: str) -> ExtractionResult:
        # Read with UTF-8, fall back to latin-1 for legacy files
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except UnicodeDecodeError:
            logger.warning(
                f"[TXT] UTF-8 decode failed for {file_path}, retrying with latin-1"
            )
            with open(file_path, "r", encoding="latin-1") as f:
                raw = f.read()

        source_type = "MD" if file_path.endswith(".md") else "TXT"
        pages: List[PageBlock] = []

        # Split on blank lines to get natural paragraphs
        raw_blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]

        # If a block is too long, split it further
        block_idx = 0
        for block in raw_blocks:
            if len(block) <= _MAX_BLOCK_CHARS:
                pages.append(
                    PageBlock(
                        text=block,
                        metadata={"block_index": block_idx, "source_type": source_type},
                    )
                )
                block_idx += 1
            else:
                # Sub-split long blocks on single newlines
                lines = block.split("\n")
                current: List[str] = []
                current_len = 0
                for line in lines:
                    if current_len + len(line) > _MAX_BLOCK_CHARS and current:
                        pages.append(
                            PageBlock(
                                text="\n".join(current),
                                metadata={
                                    "block_index": block_idx,
                                    "source_type": source_type,
                                },
                            )
                        )
                        block_idx += 1
                        current = [line]
                        current_len = len(line)
                    else:
                        current.append(line)
                        current_len += len(line)
                if current:
                    pages.append(
                        PageBlock(
                            text="\n".join(current),
                            metadata={
                                "block_index": block_idx,
                                "source_type": source_type,
                            },
                        )
                    )
                    block_idx += 1

        total_chars = sum(len(p.text) for p in pages)
        logger.info(
            f"[TXT] Extracted {len(pages)} blocks, {total_chars} chars from {file_path}"
        )
        return ExtractionResult(pages=pages, total_chars=total_chars, source_type=source_type)

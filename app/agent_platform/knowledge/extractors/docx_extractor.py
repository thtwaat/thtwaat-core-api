"""
app/agent_platform/knowledge/extractors/docx_extractor.py
DOCX text extraction using python-docx.

Groups paragraphs into logical sections based on heading styles.
Each section (or fixed-size batch of paragraphs) becomes a PageBlock
so that heading information is carried as metadata.
"""
import logging
from typing import List

from .base import BaseExtractor, ExtractionResult, PageBlock

logger = logging.getLogger(__name__)

# Number of non-heading paragraphs to group before starting a new PageBlock
_PARAGRAPHS_PER_BLOCK = 15


class DOCXExtractor(BaseExtractor):
    """Extract text from DOCX files using python-docx."""

    def extract(self, file_path: str) -> ExtractionResult:
        try:
            from docx import Document  # lazy import
        except ImportError:
            raise RuntimeError(
                "python-docx is required for DOCX extraction. "
                "Install it with: pip install python-docx>=1.1.0"
            )

        pages: List[PageBlock] = []

        try:
            doc = Document(file_path)
        except Exception as e:
            logger.error(f"[DOCX] Failed to open {file_path}: {e}")
            raise ValueError(f"DOCX extraction failed: {e}") from e

        current_heading: str = ""
        current_paragraphs: List[str] = []
        current_index: int = 0  # paragraph group index within the section

        def flush_block() -> None:
            nonlocal current_paragraphs, current_index
            text = "\n".join(current_paragraphs).strip()
            if text:
                pages.append(
                    PageBlock(
                        text=text,
                        metadata={
                            "heading": current_heading,
                            "paragraph_group": current_index,
                            "source_type": "DOCX",
                        },
                    )
                )
            current_paragraphs = []
            current_index += 1

        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ""
            text = para.text.strip()

            if not text:
                continue

            if style_name.startswith("Heading"):
                # Flush accumulated paragraphs before this heading
                flush_block()
                current_heading = text
            else:
                current_paragraphs.append(text)
                # Flush every _PARAGRAPHS_PER_BLOCK to avoid giant blocks
                if len(current_paragraphs) >= _PARAGRAPHS_PER_BLOCK:
                    flush_block()

        flush_block()  # flush any remaining

        total_chars = sum(len(p.text) for p in pages)
        logger.info(
            f"[DOCX] Extracted {len(pages)} blocks, {total_chars} chars from {file_path}"
        )
        return ExtractionResult(
            pages=pages, total_chars=total_chars, source_type="DOCX"
        )

"""
app/agent_platform/knowledge/extractors/pdf_extractor.py
PDF text extraction using pypdf.

Extracts text page-by-page; each page becomes one PageBlock so that
downstream chunkers can preserve page-number metadata.
"""
import logging
from typing import List

from .base import BaseExtractor, ExtractionResult, PageBlock

logger = logging.getLogger(__name__)


class PDFExtractor(BaseExtractor):
    """Extract text from PDF files using pypdf."""

    def extract(self, file_path: str) -> ExtractionResult:
        try:
            from pypdf import PdfReader  # lazy import — not available in all envs
        except ImportError:
            raise RuntimeError(
                "pypdf is required for PDF extraction. "
                "Install it with: pip install pypdf>=4.0.0"
            )

        pages: List[PageBlock] = []

        try:
            reader = PdfReader(file_path)
            for page_num, page in enumerate(reader.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception as e:
                    logger.warning(
                        f"[PDF] Could not extract text from page {page_num}: {e}"
                    )
                    text = ""

                if text.strip():
                    pages.append(
                        PageBlock(
                            text=text.strip(),
                            metadata={"page": page_num, "source_type": "PDF"},
                        )
                    )

        except Exception as e:
            logger.error(f"[PDF] Failed to read {file_path}: {e}")
            raise ValueError(f"PDF extraction failed: {e}") from e

        total_chars = sum(len(p.text) for p in pages)
        logger.info(
            f"[PDF] Extracted {len(pages)} pages, {total_chars} chars from {file_path}"
        )
        return ExtractionResult(pages=pages, total_chars=total_chars, source_type="PDF")

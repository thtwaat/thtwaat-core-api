"""
app/agent_platform/knowledge/extractors/base.py
Abstract base class and result dataclass for all extractors.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class PageBlock:
    """A block of extracted text from a single page/section."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    # e.g., {"page": 1, "heading": "Introduction"} for PDF
    # e.g., {"paragraph_index": 5, "style": "Heading1"} for DOCX


@dataclass
class ExtractionResult:
    """Full extraction output for one document."""
    pages: List[PageBlock]
    total_chars: int
    source_type: str  # PDF | DOCX | TXT | MD

    @property
    def full_text(self) -> str:
        """Concatenated text of all pages (used for simple chunking)."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())


class BaseExtractor(ABC):
    """Abstract extractor — all file-type extractors implement this."""

    @abstractmethod
    def extract(self, file_path: str) -> ExtractionResult:
        """Extract text from the file at *file_path* and return an ExtractionResult."""
        ...

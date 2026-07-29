"""
app/agent_platform/knowledge/extractors/factory.py
Factory that returns the right extractor based on document source_type or file extension.
"""
from .base import BaseExtractor
from .pdf_extractor import PDFExtractor
from .docx_extractor import DOCXExtractor
from .txt_extractor import TXTExtractor

_EXTRACTOR_MAP: dict[str, type[BaseExtractor]] = {
    "PDF":  PDFExtractor,
    "DOCX": DOCXExtractor,
    "TXT":  TXTExtractor,
    "MD":   TXTExtractor,  # MD is handled by TXTExtractor
    # Extension-based aliases
    ".pdf":  PDFExtractor,
    ".docx": DOCXExtractor,
    ".txt":  TXTExtractor,
    ".md":   TXTExtractor,
}


class ExtractorFactory:
    """Returns an instantiated extractor for the given source type."""

    @staticmethod
    def get(source_type: str) -> BaseExtractor:
        """
        Args:
            source_type: One of 'PDF', 'DOCX', 'TXT', 'MD' or a file extension
                         like '.pdf', '.docx', etc.

        Returns:
            An instantiated BaseExtractor subclass.

        Raises:
            ValueError: If no extractor is registered for the given source_type.
        """
        key = source_type.upper() if not source_type.startswith(".") else source_type.lower()
        cls = _EXTRACTOR_MAP.get(key) or _EXTRACTOR_MAP.get(source_type)
        if cls is None:
            raise ValueError(
                f"No extractor registered for source_type='{source_type}'. "
                f"Supported: {sorted({k for k in _EXTRACTOR_MAP if not k.startswith('.')})}."
            )
        return cls()

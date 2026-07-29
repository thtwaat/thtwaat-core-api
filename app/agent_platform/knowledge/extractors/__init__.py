"""
app/agent_platform/knowledge/extractors/__init__.py
Public interface for the text extraction package.
"""
from .factory import ExtractorFactory
from .base import BaseExtractor, ExtractionResult

__all__ = ["ExtractorFactory", "BaseExtractor", "ExtractionResult"]

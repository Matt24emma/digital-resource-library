# ebook/services/interfaces.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class Extractor(ABC):
    """Extracts text from a PDF file."""
    @abstractmethod
    def extract(self, file_path: str) -> str:
        """Return extracted plain text."""
        pass

class OCR(ABC):
    """Performs OCR on an image‑based PDF."""
    @abstractmethod
    def ocr(self, file_path: str) -> str:
        """Return OCR‑extracted text."""
        pass

class Normalizer(ABC):
    """Cleans and normalizes extracted text."""
    @abstractmethod
    def normalize(self, raw_text: str) -> str:
        """Return normalized text."""
        pass

class QualityValidator(ABC):
    """Validates text quality."""
    @abstractmethod
    def validate(self, text: str) -> Dict[str, Any]:
        """Return a dict with 'passed' (bool) and optionally 'reason'."""
        pass

class ChapterDetector(ABC):
    """Detects chapters/sections in text."""
    @abstractmethod
    def detect(self, text: str) -> List[Dict[str, Any]]:
        """
        Return a list of chapters, each with:
        {'start_index': int, 'title': str, 'level': int, ...}
        """
        pass

class ChunkGenerator(ABC):
    """Generates daily chunks based on pages per day and chapter boundaries."""
    @abstractmethod
    def generate(self, text: str, pages_per_day: int, total_pages: int, chapters: List[Dict]) -> List[Dict]:
        """
        Return list of chunks: each dict with 'content', 'page_start', 'page_end'.
        """
        pass

class AIFormatter(ABC):
    """Formats/enriches text using an AI model."""
    @abstractmethod
    def format(self, chunk_text: str, context: Optional[Dict] = None) -> str:
        """Return formatted text."""
        pass
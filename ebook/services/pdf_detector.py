# ebook/services/pdf_detector.py
import fitz  # PyMuPDF
from typing import Literal

class PdfDetector:
    @staticmethod
    def detect(file_path: str) -> Literal['text', 'image']:
        """
        Determine if PDF has selectable text.
        Returns 'text' if any page contains text, else 'image'.
        """
        doc = fitz.open(file_path)
        for page in doc:
            # Extract text; if length > threshold, assume text-based
            text = page.get_text()
            if len(text.strip()) > 50:   # heuristic
                doc.close()
                return 'text'
        doc.close()
        return 'image'
# ebook/services/quality_validator.py
from typing import Dict, Any
from .interfaces import QualityValidator

class SimpleQualityValidator(QualityValidator):
    def validate(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        word_count = len(cleaned.split())
        if word_count < 50:
            return {'passed': False, 'reason': f'Too few words ({word_count}); probably OCR failure or empty PDF.'}
        # Additional checks: ratio of uppercase, repeated lines, etc.
        # For now, assume passed.
        return {'passed': True, 'word_count': word_count}
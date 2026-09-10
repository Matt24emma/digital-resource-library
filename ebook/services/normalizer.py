# ebook/services/normalizer.py
import re
from .interfaces import Normalizer

class TextNormalizer(Normalizer):
    def normalize(self, raw_text: str) -> str:
        text = raw_text

        # Remove excessive whitespace (multiple newlines, spaces)
        text = re.sub(r'\n\s*\n', '\n\n', text)   # keep paragraph breaks
        text = re.sub(r'[ \t]+', ' ', text)

        # Remove repeated headers/footers (heuristic: identical lines on many pages)
        lines = text.splitlines()
        # Simple approach: collect line frequencies and remove lines that appear very often
        # (but careful not to remove headings). We'll keep it simple.
        # More robust: use page separators if PyMuPDF provides page breaks.
        # For brevity, we'll just remove lines that are all caps and short, repeated often.
        # In real code, we'd use page-level detection.

        # Repair broken paragraphs: join lines that don't end with punctuation.
        # This is tricky; we'll implement a basic version.
        # We'll assume paragraphs are separated by double newlines.
        paragraphs = re.split(r'\n\s*\n', text)
        repaired = []
        for para in paragraphs:
            # Join lines with space if they don't end with sentence-ending punctuation
            lines_in_para = para.splitlines()
            joined = []
            for line in lines_in_para:
                line = line.strip()
                if not line:
                    continue
                if joined:
                    # if previous line doesn't end with ., !, ? or is a heading (all caps short)
                    last = joined[-1]
                    if last and not re.search(r'[.!?…"]$', last) and not self._is_heading(last):
                        joined[-1] = last + ' ' + line
                    else:
                        joined.append(line)
                else:
                    joined.append(line)
            repaired.append(' '.join(joined))
        text = '\n\n'.join(repaired)

        # Preserve bullet lists: detect lines starting with -, *, or numbers.
        # We'll keep them as they are; normalization shouldn't change them.
        # Also preserve headings: lines that are all caps, or have numbers like 1., etc.
        # We'll not modify them.

        return text

    def _is_heading(self, line: str) -> bool:
        # Heuristic: all caps, or starts with number/roman numeral
        if re.match(r'^[IVX]+\.', line) or re.match(r'^\d+\.', line):
            return True
        if line.isupper() and len(line.split()) <= 6:
            return True
        return False
# ebook/services/chapter_detector.py
import re
from typing import List, Dict
from .interfaces import ChapterDetector

class RegexChapterDetector(ChapterDetector):
    def detect(self, text: str) -> List[Dict[str, any]]:
        lines = text.splitlines()
        chapters = []
        # Patterns for chapter headings
        patterns = [
            r'^(Chapter|CHAPTER|Part|Lesson|Module)\s+([IVX\d]+\.?[\s:]+.*)$',  # e.g., "Chapter 1: Introduction"
            r'^([IVX]+\.\s+.*)$',   # Roman numerals with dot
            r'^(\d+\.\s+.*)$',      # Number with dot
            r'^([A-Z][A-Z\s]{2,})$', # ALL CAPS SHORT HEADINGS
        ]
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            matched = False
            title = line_stripped
            level = 1
            for pat in patterns:
                m = re.match(pat, line_stripped)
                if m:
                    # If it's chapter/part, might have group captures
                    if len(m.groups()) >= 2:
                        title = m.group(2).strip()
                    else:
                        title = line_stripped
                    matched = True
                    break
            if matched:
                chapters.append({
                    'start_index': i,          # line index
                    'title': title,
                    'level': level,
                })
        return chapters
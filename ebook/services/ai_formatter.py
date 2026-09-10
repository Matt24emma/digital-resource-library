# ebook/services/ai_formatter.py
import re
from typing import Optional, Dict
from .interfaces import AIFormatter


class RuleBasedFormatter(AIFormatter):
    def format(self, chunk_text: str, context: Optional[Dict] = None) -> str:
        """
        Format text by detecting headings and paragraphs.
        """
        if not chunk_text:
            return ""

        # Split into lines
        lines = chunk_text.split("\n")
        formatted_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Check if line is a heading
            if self._is_heading(line):
                formatted_lines.append(f"\n{line}\n")
            else:
                formatted_lines.append(line)

        # Join with newline
        result = "\n".join(formatted_lines)
        # Clean up excessive newlines
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _is_heading(self, line: str) -> bool:
        """Heuristic: heading if line is all caps (or starts with number) and short."""
        if len(line) > 100:
            return False
        # Starts with number (e.g., "1.", "Chapter 1")
        if re.match(r"^(\d+\.?\s+|\w+\s+\d+)", line):
            return True
        # All uppercase letters (with some punctuation)
        if re.match(r"^[A-Z][A-Z\s\.\,\-]+$", line):
            return True
        return False

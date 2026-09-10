from typing import List, Dict, Any
from .interfaces import ChunkGenerator
import re


class PageBasedChunkGenerator(ChunkGenerator):
    def generate(
        self, text: str, pages_per_day: int, total_pages: int, chapters: List[Dict]
    ) -> List[Dict]:
        words = text.split()
        total_words = len(words)
        if total_pages <= 0:
            words_per_page = 300
        else:
            words_per_page = total_words / total_pages
        chunk_size_words = int(pages_per_day * words_per_page)

        chunks = []
        start = 0
        chunk_num = 1
        chapter_titles = [ch["title"] for ch in chapters]

        while start < total_words:
            end = min(start + chunk_size_words, total_words)
            chunk_text = " ".join(words[start:end])
            page_start = int(start / words_per_page) + 1 if words_per_page > 0 else 1
            page_end = int((end - 1) / words_per_page) + 1 if words_per_page > 0 else 1

            chapter_title = ""
            for title in chapter_titles:
                if re.search(re.escape(title), chunk_text, re.IGNORECASE):
                    chapter_title = title
                    break

            chunks.append(
                {
                    "content": chunk_text,
                    "page_start": page_start,
                    "page_end": page_end,
                    "chunk_number": chunk_num,
                    "chapter_title": chapter_title,
                    "word_count": len(chunk_text.split()),
                }
            )
            start = end
            chunk_num += 1
        return chunks

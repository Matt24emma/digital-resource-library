# ebook/services/pipeline.py
import logging
from typing import Dict, Any
from django.core.files.uploadedfile import UploadedFile
from django.core.files.storage import default_storage
from digital.models import Book, ProcessingStage, Chunk
from ebook.services.storage_service import TemporaryStorage
from ebook.services.pdf_detector import PdfDetector
from ebook.services.extractors import PyMuPDFExtractor, TesseractOCR
from ebook.services.normalizer import TextNormalizer
from ebook.services.quality_validator import SimpleQualityValidator
from ebook.services.chapter_detector import RegexChapterDetector
from ebook.services.chunk_service import PageBasedChunkGenerator
from ebook.services.ai_formatter import RuleBasedFormatter
import fitz
from django.utils import timezone
from datetime import datetime, timedelta, date  # <-- added date

logger = logging.getLogger(__name__)


def make_serializable(obj):
    """Recursively convert datetime/date objects to ISO strings."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_serializable(item) for item in obj]
    return obj


class Pipeline:
    def __init__(self):
        self.detector = PdfDetector()
        self.extractor = PyMuPDFExtractor()
        self.ocr = TesseractOCR()
        self.normalizer = TextNormalizer()
        self.validator = SimpleQualityValidator()
        self.chapter_detector = RegexChapterDetector()
        self.chunk_generator = PageBasedChunkGenerator()
        self.formatter = RuleBasedFormatter()

    def process(
        self, uploaded_file: UploadedFile, pages_per_day: int, book_id: int
    ) -> Dict[str, Any]:
        file_path = TemporaryStorage.save_uploaded_file(uploaded_file)
        book = Book.objects.get(id=book_id)
        try:
            return self._process_file(book, file_path, pages_per_day)
        finally:
            TemporaryStorage.delete_file(file_path)

    def process_from_path(
        self, file_path: str, pages_per_day: int, book_id: int
    ) -> Dict[str, Any]:
        book = Book.objects.get(id=book_id)
        return self._process_file(book, file_path, pages_per_day)

    def _process_file(
        self, book: Book, file_path: str, pages_per_day: int
    ) -> Dict[str, Any]:
        book.status = "processing"
        book.progress = 0
        book.save()
        print(f"[Pipeline] Starting processing for book {book.id}")

        try:
            # 1. PDF Detection
            print("[Pipeline] Step 1: PDF detection...")
            pdf_type = self.detector.detect(file_path)
            self._save_stage(book, "pdf_detection", {"type": pdf_type})
            book.progress = 10
            book.save()
            print(f"[Pipeline] PDF type: {pdf_type}")

            # 2. Extraction
            print("[Pipeline] Step 2: Extracting text...")
            if pdf_type == "text":
                raw_text = self.extractor.extract(file_path)
            else:
                raw_text = self.ocr.ocr(file_path)
            self._save_stage(book, "extracted_text", {"text": raw_text})
            book.progress = 30
            book.save()
            print("[Pipeline] Extraction done.")

            # 3. Normalization
            print("[Pipeline] Step 3: Normalizing text...")
            normalized_text = self.normalizer.normalize(raw_text)
            self._save_stage(book, "normalized_text", {"text": normalized_text})
            book.progress = 45
            book.save()
            print("[Pipeline] Normalization done.")

            # 4. Quality Validation
            print("[Pipeline] Step 4: Validating text quality...")
            validation_result = self.validator.validate(normalized_text)
            self._save_stage(book, "quality_validation", validation_result)
            if not validation_result["passed"]:
                book.status = "failed"
                book.progress = 100
                book.save()
                print(
                    f"[Pipeline] Validation failed: {validation_result.get('reason')}"
                )
                return {"status": "failed", "reason": validation_result.get("reason")}
            book.progress = 55
            book.save()
            print("[Pipeline] Validation passed.")

            # 5. Chapter Detection
            print("[Pipeline] Step 5: Detecting chapters...")
            chapters = self.chapter_detector.detect(normalized_text)
            self._save_stage(book, "chapters", chapters)
            book.progress = 65
            book.save()
            print(f"[Pipeline] Found {len(chapters)} chapters.")

            # 6. Chunk Generation
            print("[Pipeline] Step 6: Generating chunks...")
            doc = fitz.open(file_path)
            total_pages = doc.page_count
            doc.close()
            book.total_pages = total_pages
            book.save()

            chunks_data = self.chunk_generator.generate(
                normalized_text, pages_per_day, total_pages, chapters
            )
            self._save_stage(book, "chunks_raw", chunks_data)
            book.progress = 80
            book.save()
            print(f"[Pipeline] Generated {len(chunks_data)} raw chunks.")

            # 7. AI Formatting
            print("[Pipeline] Step 7: Formatting chunks...")
            formatted_chunks = []
            for i, chunk_dict in enumerate(chunks_data):
                formatted_text = self.formatter.format(chunk_dict["content"])
                formatted_chunks.append(
                    {
                        **chunk_dict,
                        "content": formatted_text,
                    }
                )
                if i % 10 == 0:
                    progress = 80 + int((i / len(chunks_data)) * 15)
                    book.progress = min(progress, 95)
                    book.save()
            self._save_stage(book, "formatted_chunks", formatted_chunks)
            book.progress = 95
            book.save()
            print("[Pipeline] Formatting done.")

            # 8. Save chunks with scheduled_date
            print("[Pipeline] Step 8: Saving chunks to database...")
            start_date = timezone.now().date() + timedelta(days=1)
            for idx, chunk_info in enumerate(formatted_chunks):
                scheduled_date = timezone.make_aware(
                    datetime.combine(
                        start_date + timedelta(days=idx), datetime.min.time()
                    )
                )
                Chunk.objects.create(
                    book=book,
                    chunk_number=chunk_info["chunk_number"],
                    content=chunk_info["content"],
                    page_start=chunk_info["page_start"],
                    page_end=chunk_info["page_end"],
                    chapter_title=(chunk_info.get("chapter_title") or "")[
                        :500
                    ],  # ← CHANGED
                    word_count=chunk_info.get("word_count"),
                    scheduled_date=scheduled_date,
                )
                if idx % 10 == 0:
                    progress = 95 + int((idx / len(formatted_chunks)) * 5)
                    book.progress = min(progress, 100)
                    book.save()

            book.status = "completed"
            book.progress = 100
            book.save()
            print("[Pipeline] Processing complete!")
            return {"status": "completed", "chunks": len(formatted_chunks)}

        except Exception as e:
            logger.exception("Pipeline failed for book %d", book.id)
            book.status = "failed"
            book.progress = 100
            book.save()
            print(f"[Pipeline] ERROR: {e}")
            raise

    def _save_stage(self, book, stage_name, data):
        serialized_data = make_serializable(data)
        ProcessingStage.objects.create(
            book=book,
            stage_name=stage_name,
            data=serialized_data,
        )

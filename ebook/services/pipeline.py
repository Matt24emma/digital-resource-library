# ebook/services/pipeline.py
import logging
from typing import Dict, Any
from django.core.files.uploadedfile import UploadedFile
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
from datetime import datetime, timedelta, date

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

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _fail(self, book, stage, reason, details=None):
        """
        Record a failed pipeline run with a user-readable reason.

        The reason is stored as a ProcessingStage record with
        stage_name='error' so the UI can surface it.
        """
        payload = {
            "stage": stage,
            "reason": str(reason),
            "details": details or {},
            "timestamp": timezone.now().isoformat(),
        }
        try:
            self._save_stage(book, "error", payload)
        except Exception:
            logger.exception("Failed to persist error stage for book %d", book.id)

        book.status = "failed"
        book.progress = 100
        book.save(update_fields=["status", "progress"])

        logger.warning("Pipeline FAILED for book %d at %s: %s", book.id, stage, reason)
        print(f"[Pipeline] FAILED at {stage}: {reason}")

        return {
            "status": "failed",
            "stage": stage,
            "reason": str(reason),
            "details": payload,
        }

    def _check_pdf_integrity(self, book, file_path):
        """
        Verify the PDF opens cleanly and that key pages load.

        Returns (ok: bool, reason: str | None, meta: dict)
        """
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            return False, f"Cannot open PDF: {e}", {}

        try:
            total_pages = doc.page_count
            if total_pages == 0:
                doc.close()
                return False, "PDF contains zero pages.", {"total_pages": 0}

            # Sample the first, middle, and last pages
            check_indices = sorted({0, total_pages // 2, total_pages - 1})
            unreadable = []
            for idx in check_indices:
                try:
                    doc.load_page(idx)
                except Exception as e:
                    unreadable.append({"page": idx, "error": str(e)})

            doc.close()

            if len(unreadable) == len(check_indices):
                return (
                    False,
                    "This PDF appears to be corrupted. "
                    "Its internal page structure cannot be read. "
                    "Please try a different file.",
                    {"total_pages": total_pages, "unreadable": unreadable},
                )

            return (
                True,
                None,
                {"total_pages": total_pages, "unreadable": unreadable},
            )
        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            return False, f"PDF integrity check crashed: {e}", {}

    # ------------------------------------------------------------------
    # MAIN PIPELINE
    # ------------------------------------------------------------------
    def _process_file(
        self, book: Book, file_path: str, pages_per_day: int
    ) -> Dict[str, Any]:
        book.status = "processing"
        book.progress = 0
        book.save(update_fields=["status", "progress"])
        print(f"[Pipeline] Starting processing for book {book.id}")

        try:
            # ----------------------------------------------------------
            # 1. PDF Detection
            # ----------------------------------------------------------
            print("[Pipeline] Step 1: PDF detection...")
            pdf_type = self.detector.detect(file_path)
            self._save_stage(book, "pdf_detection", {"type": pdf_type})
            book.progress = 10
            book.save(update_fields=["progress"])
            print(f"[Pipeline] PDF type: {pdf_type}")

            # ----------------------------------------------------------
            # 1b. Integrity pre-flight check
            # ----------------------------------------------------------
            print("[Pipeline] Step 1b: PDF integrity check...")
            ok, reason, meta = self._check_pdf_integrity(book, file_path)
            self._save_stage(
                book,
                "pdf_integrity",
                {"ok": ok, "reason": reason, **meta},
            )
            if not ok:
                return self._fail(book, "pdf_integrity", reason, meta)

            book.progress = 15
            book.save(update_fields=["progress"])
            print("[Pipeline] PDF integrity OK.")

            # ----------------------------------------------------------
            # 2. Extraction
            # ----------------------------------------------------------
            print("[Pipeline] Step 2: Extracting text...")
            try:
                if pdf_type == "text":
                    raw_text = self.extractor.extract(file_path)
                else:
                    raw_text = self.ocr.ocr(file_path)
            except NotImplementedError as e:
                return self._fail(book, "extraction", str(e), {"pdf_type": pdf_type})
            except ValueError as e:
                return self._fail(book, "extraction", str(e), {"pdf_type": pdf_type})
            except Exception as e:
                return self._fail(
                    book,
                    "extraction",
                    f"Text extraction failed: {e}",
                    {"pdf_type": pdf_type},
                )

            self._save_stage(book, "extracted_text", {"text": raw_text})
            book.progress = 30
            book.save(update_fields=["progress"])
            print("[Pipeline] Extraction done.")

            # ----------------------------------------------------------
            # 3. Normalization
            # ----------------------------------------------------------
            print("[Pipeline] Step 3: Normalizing text...")
            normalized_text = self.normalizer.normalize(raw_text)
            self._save_stage(book, "normalized_text", {"text": normalized_text})
            book.progress = 45
            book.save(update_fields=["progress"])
            print("[Pipeline] Normalization done.")

            # ----------------------------------------------------------
            # 4. Quality Validation
            # ----------------------------------------------------------
            print("[Pipeline] Step 4: Validating text quality...")
            validation_result = self.validator.validate(normalized_text)
            self._save_stage(book, "quality_validation", validation_result)
            if not validation_result.get("passed"):
                return self._fail(
                    book,
                    "quality_validation",
                    validation_result.get("reason", "Text quality validation failed."),
                    {"validation": validation_result},
                )
            book.progress = 55
            book.save(update_fields=["progress"])
            print("[Pipeline] Validation passed.")

            # ----------------------------------------------------------
            # 5. Chapter Detection
            # ----------------------------------------------------------
            print("[Pipeline] Step 5: Detecting chapters...")
            chapters = self.chapter_detector.detect(normalized_text)
            self._save_stage(book, "chapters", chapters)
            book.progress = 65
            book.save(update_fields=["progress"])
            print(f"[Pipeline] Found {len(chapters)} chapters.")

            # ----------------------------------------------------------
            # 6. Chunk Generation
            # ----------------------------------------------------------
            print("[Pipeline] Step 6: Generating chunks...")
            doc = fitz.open(file_path)
            total_pages = doc.page_count
            doc.close()
            book.total_pages = total_pages
            book.save(update_fields=["total_pages"])

            chunks_data = self.chunk_generator.generate(
                normalized_text, pages_per_day, total_pages, chapters
            )
            self._save_stage(book, "chunks_raw", chunks_data)
            book.progress = 80
            book.save(update_fields=["progress"])
            print(f"[Pipeline] Generated {len(chunks_data)} raw chunks.")

            if not chunks_data:
                return self._fail(
                    book,
                    "chunk_generation",
                    "No readable chunks could be generated from this PDF. "
                    "It may be empty or contain only images.",
                    {},
                )

            # ----------------------------------------------------------
            # 7. Formatting
            # ----------------------------------------------------------
            print("[Pipeline] Step 7: Formatting chunks...")
            formatted_chunks = []
            for i, chunk_dict in enumerate(chunks_data):
                formatted_text = self.formatter.format(chunk_dict["content"])
                formatted_chunks.append({**chunk_dict, "content": formatted_text})
                if i % 10 == 0:
                    progress = 80 + int((i / len(chunks_data)) * 15)
                    book.progress = min(progress, 95)
                    book.save(update_fields=["progress"])
            self._save_stage(book, "formatted_chunks", formatted_chunks)
            book.progress = 95
            book.save(update_fields=["progress"])
            print("[Pipeline] Formatting done.")

            # ----------------------------------------------------------
            # 8. Save chunks
            # ----------------------------------------------------------
            print("[Pipeline] Step 8: Saving chunks to database...")
            start_date = timezone.now().date() + timedelta(days=1)
            saved = 0

            for idx, chunk_info in enumerate(formatted_chunks):
                scheduled_date = timezone.make_aware(
                    datetime.combine(
                        start_date + timedelta(days=idx),
                        datetime.min.time(),
                    )
                )
                try:
                    Chunk.objects.create(
                        book=book,
                        chunk_number=chunk_info["chunk_number"],
                        content=chunk_info["content"],
                        page_start=chunk_info["page_start"],
                        page_end=chunk_info["page_end"],
                        chapter_title=(chunk_info.get("chapter_title") or "")[:500],
                        word_count=chunk_info.get("word_count"),
                        scheduled_date=scheduled_date,
                    )
                    saved += 1
                except Exception as e:
                    logger.exception(
                        "Failed to save chunk %d for book %d", idx, book.id
                    )
                    return self._fail(
                        book,
                        "save_chunk",
                        f"Failed to save chunk #{idx + 1}: {e}",
                        {"chunk_number": chunk_info.get("chunk_number")},
                    )

                if idx % 10 == 0:
                    progress = 95 + int((idx / len(formatted_chunks)) * 5)
                    book.progress = min(progress, 100)
                    book.save(update_fields=["progress"])

            book.status = "completed"
            book.progress = 100
            book.save(update_fields=["status", "progress"])
            print(f"[Pipeline] Processing complete! Saved {saved} chunks.")
            return {"status": "completed", "chunks": saved}

        except Exception as e:
            logger.exception("Unexpected pipeline failure for book %d", book.id)
            return self._fail(book, "unknown", str(e), {})

    def _save_stage(self, book, stage_name, data):
        serialized_data = make_serializable(data)
        ProcessingStage.objects.create(
            book=book,
            stage_name=stage_name,
            data=serialized_data,
        )

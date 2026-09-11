# ebook/services/extractors.py
import fitz
from .interfaces import Extractor, OCR


class PyMuPDFExtractor(Extractor):
    """
    Extract text from PDF using PyMuPDF.

    Resilient to partially-corrupt PDFs: skips pages that fail to load
    rather than aborting the entire extraction.
    """

    def extract(self, file_path: str) -> str:
        doc = fitz.open(file_path)
        text_parts = []
        total_pages = doc.page_count
        bad_pages = []

        for i in range(total_pages):
            try:
                page = doc.load_page(i)
                page_text = page.get_text()
                if page_text:
                    text_parts.append(page_text)
            except Exception as e:
                print(f"[Extractor] Skipping page {i}: {e}")
                bad_pages.append({"page": i, "error": str(e)})
                continue

        doc.close()

        if bad_pages:
            print(
                f"[Extractor] Skipped {len(bad_pages)} bad pages "
                f"out of {total_pages}: {bad_pages}"
            )

        if not text_parts:
            raise ValueError(
                f"PDF has no readable pages. All {total_pages} pages failed to load."
            )

        return "\n".join(text_parts)


class TesseractOCR(OCR):
    """
    Placeholder for actual OCR (e.g., pytesseract + pdf2image).
    In production, use Tesseract or a cloud OCR service.
    """

    def ocr(self, file_path: str) -> str:
        raise NotImplementedError(
            "OCR not implemented yet. This PDF appears to be image-based "
            "(scanned). Please upload a text-based PDF."
        )

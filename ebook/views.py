# ebook/views.py
import threading
import logging
import tempfile
import os
from datetime import date, timedelta
import filetype
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from digital.models import Book, Chunk, ProcessingStage, ChapterSummary
from digital.utils import log_activity
from ebook.services.pipeline import Pipeline

logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================
def download_file_to_temp(file_field):
    """Download a file from storage to a temporary file and return the path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_path = temp_file.name
    temp_file.close()

    with file_field.open("rb") as source_file:
        with open(temp_path, "wb") as dest_file:
            for chunk in source_file.chunks():
                dest_file.write(chunk)
    return temp_path


def _get_error_info(book):
    """
    Return the most recent error stage for a failed book, or None.

    Returns a dict:
        {
            "stage": "extraction",
            "reason": "This PDF appears to be corrupted...",
            "timestamp": "2026-09-11T08:36:30Z",
            "details": {...},
        }
    """
    if book.status != "failed":
        return None

    stage = (
        ProcessingStage.objects.filter(book=book, stage_name="error")
        .order_by("-created_at")
        .first()
    )
    if not stage:
        return {
            "stage": "unknown",
            "reason": "Processing failed for an unknown reason. Please try again.",
            "timestamp": None,
            "details": {},
        }

    data = stage.data or {}
    return {
        "stage": data.get("stage", "unknown"),
        "reason": data.get("reason", "Processing failed."),
        "timestamp": data.get("timestamp"),
        "details": data.get("details", {}),
    }


# ============================================================
# UPLOAD
# ============================================================
@login_required
def upload_view(request):
    if request.method == "POST":
        uploaded_file = request.FILES.get("pdf")
        pages_per_day = request.POST.get("pages_per_day")

        if not uploaded_file or not pages_per_day:
            messages.error(request, "Please provide both PDF and pages per day.")
            return render(request, "ebook/ebook.html")

        # ---- Size checks ----
        if uploaded_file.size == 0:
            messages.error(
                request, "The uploaded file is empty. Please choose a valid PDF."
            )
            return render(request, "ebook/ebook.html")

        if uploaded_file.size > 50 * 1024 * 1024:
            messages.error(request, "File size exceeds 50MB limit.")
            return render(request, "ebook/ebook.html")

        # ---- Magic byte check: confirm it's really a PDF ----
        # The browser-provided Content-Type and the file extension can be
        # spoofed. Only the file's magic bytes are trustworthy.
        header = uploaded_file.read(2048)
        uploaded_file.seek(0)  # rewind so the pipeline can read it later

        kind = filetype.guess(header)
        if kind is None or kind.mime != "application/pdf":
            detected = kind.mime if kind else "unknown"
            messages.error(
                request,
                f"That file isn't a valid PDF (detected: {detected}). "
                "Please upload a genuine PDF file.",
            )
            return render(request, "ebook/ebook.html")

        # ---- Filename sanitization ----
        # Strip directory components and force a .pdf extension.
        # Prevents path traversal (e.g. "../../etc/passwd") and
        # ensures Cloudinary always sees a safe filename.
        safe_name = os.path.basename(uploaded_file.name)
        if not safe_name.lower().endswith(".pdf"):
            safe_name = f"{safe_name}.pdf"

        # Truncate to a reasonable length (Cloudinary caps at 255)
        if len(safe_name) > 200:
            base, ext = os.path.splitext(safe_name)
            safe_name = base[: 200 - len(ext)] + ext

        # ---- Pages per day ----
        try:
            pages_per_day = int(pages_per_day)
        except (TypeError, ValueError):
            messages.error(request, "Pages per day must be a number.")
            return render(request, "ebook/ebook.html")

        if pages_per_day < 1 or pages_per_day > 1000:
            messages.error(request, "Pages per day must be between 1 and 1000.")
            return render(request, "ebook/ebook.html")

        # ---- Create the Book record ----
        # Attach the safe filename to the uploaded file before saving
        uploaded_file.name = safe_name

        book = Book.objects.create(
            user=request.user,
            file=uploaded_file,
            pages_per_day=pages_per_day,
            status="processing",
            title=safe_name,
        )

        log_activity(request.user, "upload_book", f"Uploaded book: {book.title}")

        # ---- Background pipeline thread ----
        def run_pipeline():
            temp_path = None
            try:
                temp_path = download_file_to_temp(book.file)
                logger.info(
                    "Processing book %d from temp path: %s",
                    book.id,
                    temp_path,
                )
                pipeline = Pipeline()
                result = pipeline.process_from_path(temp_path, pages_per_day, book.id)
                logger.info("Pipeline result: %s", result)
            except Exception as e:
                logger.exception("Pipeline crashed for book %d", book.id)
                book.status = "failed"
                book.progress = 100
                book.save(update_fields=["status", "progress"])
                try:
                    ProcessingStage.objects.create(
                        book=book,
                        stage_name="error",
                        data={
                            "stage": "unknown",
                            "reason": f"Unexpected error: {e}",
                            "details": {},
                        },
                    )
                except Exception:
                    logger.exception(
                        "Failed to record last-resort error stage for book %d",
                        book.id,
                    )
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        messages.success(request, "Book uploaded! Processing started.")
        return redirect("status", book_id=book.id)

    return render(request, "ebook/ebook.html")


# ============================================================
# PROGRESS (JSON polled by the frontend)
# ============================================================
@login_required
def progress_view(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    error_info = _get_error_info(book)

    payload = {
        "status": book.status,
        "progress": book.progress,
        "total_chunks": book.chunks.count(),
        "error": error_info,  # None if not failed
    }
    return JsonResponse(payload)


# ============================================================
# STATUS PAGE (full HTML render)
# ============================================================
@login_required
def status_view(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    chunks = book.chunks.all() if book.status == "completed" else []
    for chunk in chunks:
        chunk.est_minutes = max(1, round((chunk.word_count or 300) / 200))

    estimated_completion = None
    if chunks and book.status == "completed":
        estimated_completion = date.today() + timedelta(days=len(chunks))

    chapters_data = None
    if book.status == "completed":
        stage = ProcessingStage.objects.filter(book=book, stage_name="chapters").first()
        if stage:
            chapters_data = stage.data

    # ---- Error passthrough ----
    error_info = _get_error_info(book)

    context = {
        "book": book,
        "chunks": chunks,
        "chapters": chapters_data,
        "estimated_completion": estimated_completion,
        "total_chunks": len(chunks),
        "first_unread": 1,
        "error": error_info,  # None if not failed
    }
    return render(request, "ebook/review.html", context)


# ============================================================
# STATUS DATA (JSON — used if the frontend polls stages)
# ============================================================
@login_required
@require_GET
def status_data_view(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    stages = ProcessingStage.objects.filter(book=book).values(
        "stage_name", "created_at"
    )
    error_info = _get_error_info(book)

    data = {
        "status": book.status,
        "progress": book.progress,
        "stages": list(stages),
        "total_pages": book.total_pages,
        "error": error_info,
    }
    return JsonResponse(data)


# ============================================================
# READING SESSION
# ============================================================
@login_required
def reading_view(request, book_id, chunk_id):
    book = get_object_or_404(Book, id=book_id)
    chunk = get_object_or_404(Chunk, id=chunk_id, book=book)
    total_chunks = book.chunks.count()
    chunk.est_minutes = max(1, round((chunk.word_count or 300) / 200))

    summary = ChapterSummary.objects.filter(
        book=book, chapter_title=chunk.chapter_title
    ).first()

    next_chunk = Chunk.objects.filter(
        book=book, chunk_number=chunk.chunk_number + 1
    ).first()

    prev_chunk = Chunk.objects.filter(
        book=book, chunk_number=chunk.chunk_number - 1
    ).first()

    context = {
        "book": book,
        "chunk": chunk,
        "total_chunks": total_chunks,
        "next_chunk": next_chunk,
        "previous_chunk": prev_chunk,
        "summary": summary,
    }
    return render(request, "ebook/reading.html", context)

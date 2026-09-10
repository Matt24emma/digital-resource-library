# ebook/views.py
import threading
import logging
import tempfile
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from datetime import date, timedelta

from digital.models import Book, Chunk, ProcessingStage, ChapterSummary
from ebook.services.pipeline import Pipeline

logger = logging.getLogger(__name__)


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
from digital.utils import log_activity

import threading
import os
from django.shortcuts import redirect, render
from django.contrib import messages
from .models import Book  # adjust as per your project
from digital.utils import log_activity  # import the log_activity utility


@login_required
def upload_view(request):
    if request.method == "POST":
        uploaded_file = request.FILES.get("pdf")
        pages_per_day = request.POST.get("pages_per_day")
        if uploaded_file and pages_per_day:
            if uploaded_file.size == 0:
                messages.error(
                    request, "The uploaded file is empty. Please choose a valid PDF."
                )
                return render(request, "ebook/ebook.html")
            if uploaded_file.size > 50 * 1024 * 1024:
                messages.error(request, "File size exceeds 50MB limit.")
                return render(request, "ebook/ebook.html")
            pages_per_day = int(pages_per_day)

            book = Book.objects.create(
                user=request.user,
                file=uploaded_file,
                pages_per_day=pages_per_day,
                status="processing",
                title=uploaded_file.name,
            )

            # ====== LOG THE ACTIVITY ======
            log_activity(request.user, "upload_book", f"Uploaded book: {book.title}")

            # ====== THREADING PIPELINE (as originally provided) ======
            def run_pipeline():
                temp_path = None
                try:
                    # Download file to temp
                    temp_path = download_file_to_temp(book.file)
                    logger.info(
                        f"Processing book {book.id} from temp path: {temp_path}"
                    )
                    pipeline = Pipeline()
                    result = pipeline.process_from_path(
                        temp_path, pages_per_day, book.id
                    )
                    logger.info(f"Pipeline result: {result}")
                except Exception as e:
                    logger.exception(f"Pipeline failed for book {book.id}")
                    book.status = "failed"
                    book.progress = 100
                    book.save()
                finally:
                    if temp_path and os.path.exists(temp_path):
                        os.unlink(temp_path)

            thread = threading.Thread(target=run_pipeline)
            thread.start()

            messages.success(request, "Book uploaded! Processing started.")
            return redirect("status", book_id=book.id)
        else:
            messages.error(request, "Please provide both PDF and pages per day.")
    return render(request, "ebook/ebook.html")


@login_required
def progress_view(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    return JsonResponse(
        {
            "status": book.status,
            "progress": book.progress,
            "total_chunks": book.chunks.count(),
        }
    )


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
    context = {
        "book": book,
        "chunks": chunks,
        "chapters": chapters_data,
        "estimated_completion": estimated_completion,
        "total_chunks": len(chunks),
        "first_unread": 1,
    }
    return render(request, "ebook/review.html", context)


@require_GET
def status_data_view(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    stages = ProcessingStage.objects.filter(book=book).values(
        "stage_name", "created_at"
    )
    data = {
        "status": book.status,
        "stages": list(stages),
        "total_pages": book.total_pages,
    }
    return JsonResponse(data)

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
    return render(request, "ebook/reading.html", context)  # <- use ebook/reading.html

# ebook/tasks.py
from digital.models import Book, Chunk, ProcessingStage
from ebook.services.pipeline import Pipeline
import tempfile
import os
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from digital.models import Subscription, UserPreference
import json
from twilio.rest import Client
from django.core.mail import EmailMultiAlternatives
from django.utils.safestring import mark_safe
import re


#@shared_task
def process_book_async(book_id, file_name, pages_per_day):
    """
    Process a book PDF: download from storage, run pipeline, save chunks.
    """
    book = Book.objects.get(id=book_id)
    temp_path = None

    try:
        # Open the file from storage
        with book.file.open("rb") as source_file:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                for chunk in source_file.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

        # Run the pipeline
        pipeline = Pipeline()
        result = pipeline.process_from_path(temp_path, pages_per_day, book_id)
        return result

    finally:
        # Clean up temporary file
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def send_daily_chunks():
    today = timezone.now().date()
    chunks = Chunk.objects.filter(
        scheduled_date__date=today, delivered=False
    ).select_related("book__user")
    count = 0

    for chunk in chunks:
        user = chunk.book.user
        subscription, _ = Subscription.objects.get_or_create(user=user)

        if subscription.is_premium():
            try:
                prefs = user.preferences
                if prefs.channel == "whatsapp":
                    send_chunk_whatsapp(user, chunk)
                    chunk.delivered = True
                    chunk.save()
                    count += 1
                elif prefs.channel == "email":
                    send_chunk_email(user, chunk)
                    chunk.delivered = True
                    chunk.save()
                    count += 1
            except UserPreference.DoesNotExist:
                # Default to email
                send_chunk_email(user, chunk)
                chunk.delivered = True
                chunk.save()
                count += 1

    return f"Sent {count} chunks"


def send_chunk_email(user, chunk):
    """Send a clean, formatted HTML email with the daily chunk."""
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
    subject = f"📖 Day {chunk.chunk_number}: {chunk.book.title}"

    context = {
        "user": user,
        "chunk": chunk,
        "book": chunk.book,
        "site_url": site_url,
        "summary_url": f"{site_url}/Resources/summaryForm/?book_id={chunk.book.id}&chunk_id={chunk.id}",
        "reading_url": f"{site_url}/Resources/reading/{chunk.book.id}/{chunk.id}/",
        "chunk_html": _paragraphize(chunk.content),
        "pages": f"{chunk.page_start}–{chunk.page_end}",
    }

    html_message = render_to_string("ebook/email_chunk.html", context)
    plain_message = strip_tags(html_message)

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_message, "text/html")
    email.send(fail_silently=False)


import requests
import json
from django.conf import settings


def send_chunk_whatsapp(user, chunk):
    url = f"https://graph.facebook.com/{settings.META_API_VERSION}/{settings.META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    # Get the user's WhatsApp number (format: '2349073630945' without '+')
    phone_number = user.preferences.phone_number
    if phone_number.startswith("+"):
        phone_number = phone_number[1:]

    # Use the SAFE, pre-approved "Order Confirmation" test template
    template_name = "order_confirmation"

    # The "Order Confirmation" template expects:
    # {{1}} = Order Number
    # {{2}} = Date/Time
    # {{3}} = Item Name
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": chunk.book.title,
                        },  # Order Number (substituting)
                        {
                            "type": "text",
                            "text": f"Day {chunk.chunk_number}",
                        },  # Date/Time (substituting)
                        {
                            "type": "text",
                            "text": f"{chunk.book.title} - Day {chunk.chunk_number}",
                        },  # Item Name (substituting)
                    ],
                }
            ],
        },
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Meta API Error: {response.text}")

    return response.json()["messages"][0]["id"]


def _paragraphize(text):
    """Wrap text in justified paragraphs with inline spacing for email clients."""
    if not text:
        return ""

    if re.search(r"<[^>]+>", text):
        # Already HTML — return as-is
        return mark_safe(text)

    if "\n\n" in text:
        paragraphs = text.split("\n\n")
    elif "\n" in text:
        paragraphs = text.split("\n")
    else:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        paragraphs = [
            " ".join(sentences[i : i + 3]) for i in range(0, len(sentences), 3)
        ]

    p_style = (
        "margin:0 0 20px 0; font-size:16px; line-height:1.8; color:#0F172A; "
        "text-align:justify; text-justify:inter-word; "
        "-webkit-hyphens:auto; -ms-hyphens:auto; hyphens:auto;"
    )
    return mark_safe(
        "".join(
            f'<p style="{p_style}">{p.strip()}</p>' for p in paragraphs if p.strip()
        )
    )


def send_chunk_email(user, chunk):
    """Send a clean, formatted HTML email with the daily chunk."""
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
    subject = f"📖 Day {chunk.chunk_number}: {chunk.book.title}"

    context = {
        "user": user,
        "chunk": chunk,
        "book": chunk.book,
        "site_url": site_url,
        "summary_url": f"{site_url}/Resources/summaryForm/?book_id={chunk.book.id}&chunk_id={chunk.id}",
        "reading_url": f"{site_url}/Resources/reading/{chunk.book.id}/{chunk.id}/",
        "plan_url": f"{site_url}/Resources/book/{chunk.book.id}/",  # ← reading plan URL
        "chunk_html": _paragraphize(chunk.content),
        "pages": f"{chunk.page_start}–{chunk.page_end}",
    }

    html_message = render_to_string("ebook/email_chunk.html", context)
    plain_message = strip_tags(html_message)

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_message, "text/html")
    email.send(fail_silently=False)

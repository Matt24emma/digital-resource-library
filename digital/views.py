from django.shortcuts import redirect, render, get_object_or_404
from .models import (
    Admin,
    Lead,
    Resource,
    Download,
    Category,
    UserPreference,
    UserCardGeneration,
    UserProfile,
    LeadVisit,
    PageVisit,
)
import hmac
from django_ratelimit.decorators import ratelimit
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from io import BytesIO


from django.contrib.auth.models import User
from django.db.models import F
from django.http import FileResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
import csv

from .forms import CustomUserCreationForm

from django.contrib.auth.forms import UserCreationForm
from django.core.mail import send_mail
from .models import EmailVerification
from django.core.files.base import ContentFile
import base64
from io import BytesIO
from PIL import Image
import re
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum, Avg


from django.core.paginator import Paginator
from django.db.models import Count, Q
from .models import SubscriptionPlan  # Ensure this is imported


import json
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from digital.models import Chunk
import secrets
from .models import SubscriptionPlan, Payment, PaymentEvent, Subscription, Invoice
from django.db.models import Sum, Count
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from .forms import ChapterSummaryForm
from .models import ChapterSummary, DownloadUsage, Subscription, Book

from django.conf import settings
import requests
from django.conf import settings
from digital.utils import log_activity
from .models import ActivityLog

from django.core.paginator import Paginator
from .utils.pdf_generator import generate_summary_pdf, generate_category_summary_pdf
from django.http import HttpResponseForbidden
from digital.utils.pdf_generator import (
    generate_summary_pdf,
    generate_category_summary_pdf,
)
from ebook.tasks import send_chunk_whatsapp, send_chunk_email

def landingpage(request):
    return render(
        request,
        "digital/landingpage.html",
        {
            "is_public_page": True,
        },
    )


from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt


from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Book, ChapterSummary
import hashlib
import json
from django.http import HttpResponse

import hmac
import json
import hashlib
import logging
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """
    Handle Paystack webhook events (charge.success, charge.failed, etc.).

    Verifies the signature using HMAC-SHA512 with the secret key.
    The signature header is compared in constant time to prevent timing
    attacks.
    """
    payload = request.body
    signature = request.headers.get("x-paystack-signature", "")

    # ---- Guard: secret key must be configured ----
    if not settings.PAYSTACK_SECRET_KEY:
        logger.error("PAYSTACK_SECRET_KEY is not configured — refusing webhook.")
        return HttpResponse(status=500)

    # ---- Guard: signature header must be present ----
    if not signature:
        logger.warning("Paystack webhook received with no signature header.")
        return HttpResponse(status=401)

    # ---- Compute expected signature (HMAC-SHA512) ----
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()

    # ---- Constant-time comparison ----
    if not hmac.compare_digest(signature, expected):
        logger.warning("Paystack webhook signature mismatch — rejecting.")
        return HttpResponse(status=401)

    # ---- Parse event ----
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    # ---- Handle successful charge ----
    if event.get("event") == "charge.success":
        data = event["data"]
        reference = data["reference"]
        user_id = data["metadata"].get("user_id")

        if (
            user_id
            and not Payment.objects.filter(
                reference=reference, status="success"
            ).exists()
        ):
            from django.contrib.auth.models import User

            try:
                user = User.objects.get(id=user_id)
                Payment.objects.create(
                    user=user,
                    amount=data["amount"] / 100,
                    currency=data.get("currency", "NGN"),
                    reference=reference,
                    status="success",
                    transaction_date=timezone.now(),
                    metadata={"webhook": True},
                )

                # ---- Activate subscription ----
                subscription, _ = Subscription.objects.get_or_create(user=user)
                premium_plan, _ = SubscriptionPlan.objects.get_or_create(
                    slug="premium",
                    defaults={
                        "name": "Premium",
                        "monthly_price": 100.00,
                        "currency": "NGN",
                    },
                )
                subscription.plan = premium_plan
                subscription.status = "active"
                subscription.active = True
                subscription.current_period_start = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.save()

                logger.info(
                    "Paystack webhook: activated Premium for user %d " "(ref=%s)",
                    user.id,
                    reference,
                )

            except User.DoesNotExist:
                logger.warning(
                    "Paystack webhook: user_id=%s not found (ref=%s)",
                    user_id,
                    reference,
                )

    return HttpResponse(status=200)


@login_required
@require_POST
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)
    book.delete()
    return JsonResponse({'success': True})

@login_required
@require_POST
def delete_summary(request, pk):
    # Since ChapterSummary doesn't have a direct user field, use book__user
    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)
    summary.delete()
    return JsonResponse({'success': True})


@login_required
def reading_plans(request):
    books_list = (
        Book.objects.filter(user=request.user, file__isnull=False)
        .annotate(chunk_count=Count("chunks"))
        .filter(chunk_count__gt=0)  # Only books with at least one chunk
        .order_by("-created_at")
    )

    total_books = books_list.count()
    total_reading = 0
    total_completed = 0

    for book in books_list:
        chunks = book.chunks.all()
        total_chunks = chunks.count()
        read_chunks = chunks.filter(is_read=True).count()
        book.total_chunks = total_chunks
        book.progress = (
            int((read_chunks / total_chunks * 100)) if total_chunks > 0 else 0
        )
        book.delivered_count = chunks.filter(delivered=True).count()
        book.is_scheduled = book.is_scheduled

        if book.progress == 100:
            total_completed += 1
        elif book.progress > 0:
            total_reading += 1
        book.days_to_finish = total_chunks

    paginator = Paginator(books_list, 10)
    page_number = request.GET.get("page")
    books = paginator.get_page(page_number)

    context = {
        "books": books,
        "total_books": total_books,
        "total_reading": total_reading,
        "total_completed": total_completed,
    }
    return render(request, "digital/dashboard/reading_plans.html", context)


@login_required
def book_reading_plan(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    if not book.file or not book.chunks.exists():
        messages.error(request, "This book has not been processed yet.")
        return redirect("reading_plans")

    chunks = book.chunks.all().order_by("chunk_number")
    total_chunks = chunks.count()
    read_chunks = chunks.filter(is_read=True).count()
    progress = int((read_chunks / total_chunks * 100)) if total_chunks > 0 else 0

    context = {
        "book": book,
        "chunks": chunks,
        "total_chunks": total_chunks,
        "read_chunks": read_chunks,
        "progress": progress,
        "first_unread": chunks.filter(is_read=False).first(),
    }
    return render(request, "digital/dashboard/reading-session.html", context)


from django.http import JsonResponse


@login_required
def mark_chunk_read(request, chunk_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    chunk = get_object_or_404(Chunk, id=chunk_id, book__user=request.user)
    chunk.is_read = True
    chunk.save()
    book = chunk.book
    total = book.chunks.count()
    read_count = book.chunks.filter(is_read=True).count()
    progress = int((read_count / total) * 100) if total > 0 else 0
    return JsonResponse(
        {
            "success": True,
            "progress": progress,
            "read_count": read_count,
            "total": total,
            "message": f"Congratulations! You've completed {read_count} of {total} chunks.",
        }
    )


@login_required
def all_summaries(request):
    summaries_list = ChapterSummary.objects.filter(book__user=request.user).select_related('book', 'category').order_by('-created_at')

    # Category filter
    category_id = request.GET.get('category')
    if category_id:
        summaries_list = summaries_list.filter(category_id=category_id)

    categories = Category.objects.filter(user=request.user)

    paginator = Paginator(summaries_list, 10)
    page_number = request.GET.get('page')
    summaries = paginator.get_page(page_number)

    context = {
        'summaries': summaries,
        'categories': categories,
        'selected_category': int(category_id) if category_id else None,
    }
    return render(request, 'digital/dashboard/summaries_list.html', context)

from django.core.paginator import Paginator


@login_required
def manage_categories(request):
    all_categories = Category.objects.filter(user=request.user).order_by("name")

    # Paginate - 6 categories per page
    paginator = Paginator(all_categories, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # CORRECT PREMIUM CHECK for your Subscription model
    is_premium = False
    if hasattr(request.user, "subscription"):
        is_premium = request.user.subscription.is_premium()

    return render(
        request,
        "digital/dashboard/categories.html",
        {
            "categories": page_obj,
            "page_obj": page_obj,
            "is_premium": is_premium,
        },
    )


# New View to handle the Modal
@login_required
def category_contents(request, category_id):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    # related_name from ChapterSummary is "summaries"
    summaries = category.summaries.all()

    data = []
    for s in summaries:
        data.append(
            {
                "title": (
                    s.chapter_title
                    if s.chapter_title
                    else (s.book.title if s.book else "Untitled")
                ),
                "image_url": s.card_image.url if s.card_image else "",
            }
        )
    return JsonResponse({"contents": data})


# New View to handle the Edit Modal
@login_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            category.name = name
            category.slug = slugify(name)  # Since your model has slugify
            category.save()
            return redirect("manage_categories")
    return redirect("manage_categories")


@login_required
def update_preferences(request):
    user = request.user
    prefs, created = UserPreference.objects.get_or_create(user=user)

    if request.method == "POST":
        # Initialize variables
        delivery_time = None
        channel = None
        phone_number = ""

        # Check if JSON or form data
        if request.headers.get("Content-Type") == "application/json":
            import json

            data = json.loads(request.body)
            delivery_time = data.get("delivery_time")
            channel = data.get("channel")
            phone_number = data.get("phone_number", "")
        else:
            delivery_time = request.POST.get("delivery_time")
            channel = request.POST.get("channel")
            phone_number = request.POST.get("phone_number", "")

        if delivery_time:
            prefs.delivery_time = delivery_time
        if channel in ["email", "whatsapp"]:
            prefs.channel = channel
        if channel == "whatsapp" and phone_number:
            prefs.phone_number = phone_number
        prefs.save()

        if request.headers.get("Content-Type") == "application/json":
            return JsonResponse({"success": True})
        else:
            messages.success(request, "Preferences updated!")
            return redirect("setting")

    return render(request, "digital/dashboard/settings.html", {"prefs": prefs})


@login_required
def delete_scheduled_book(request, book_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    book = get_object_or_404(Book, id=book_id, user=request.user)
    # Delete all chunks first (cascade will handle if set, but we can do explicit)
    book.chunks.all().delete()
    book.delete()
    return JsonResponse({"success": True})


@login_required
def create_category(request):
    if request.method == "POST":
        name = request.POST.get('name')
        if name:
            Category.objects.get_or_create(user=request.user, name=name)
            messages.success(request, f'Category "{name}" created.')
        return redirect('manage_categories')
    return render(request, 'digital/dashboard/categories.html')

@login_required
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == "POST":
        category.delete()
        messages.success(request, f'Category "{category.name}" deleted.')
        return redirect('manage_categories')
    return render(request, 'digital/dashboard/delete_category.html', {'category': category})


def admin_required(view_func):
    """
    Decorator that restricts access to superusers only.
    Non‑superusers are redirected to the login page.
    """
    decorated_view = user_passes_test(
        lambda u: u.is_authenticated and u.is_superuser,
        login_url="login",  # named URL of the login page
        redirect_field_name="next",
    )(view_func)
    return decorated_view


from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm


@login_required
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)  # Keep user logged in
            messages.success(request, "Your password was successfully updated!")
            return redirect("profile")  # or any user-facing page
        else:
            messages.error(request, "Please correct the error below.")
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, "digital/change_password.html", {"form": form})


def download_resource(request, slug):
    resource = get_object_or_404(Resource, slug=slug)
    if not request.session.get("lead_verified"):
        return redirect("leads", slug=slug)

    lead_id = request.session.get("lead_id")
    lead = get_object_or_404(Lead, id=lead_id)

    # Log the visit
    source = request.GET.get("source", "direct")
    if source not in dict(LeadVisit.SOURCE_CHOICES):
        source = "direct"
    LeadVisit.objects.create(
        lead=lead,
        source=source,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Try opening file first
    try:
        file = resource.file.open("rb")
    except Exception as e:
        print("Download error:", e)
        return HttpResponse("File unavailable", status=404)

    # Record the download
    Download.objects.create(lead=lead, resource=resource)
    Resource.objects.filter(pk=resource.pk).update(
        most_downloaded=F("most_downloaded") + 1
    )

    return FileResponse(
        file,
        as_attachment=True,
        filename=resource.file.name.split("/")[-1],
    )


def home(request):
    # ---- Existing resource logic ----
    resources = Resource.objects.order_by("-created_at")
    paginator = Paginator(resources, 5)
    page_number = request.GET.get("page")
    digital_resources = paginator.get_page(page_number)
    top_downloaded_resources = Resource.objects.order_by("-most_downloaded")[:5]

    # ---- Track page visit ----
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key

    # Determine traffic source from referrer
    referrer = request.META.get("HTTP_REFERER", "")
    ref_lower = referrer.lower()
    source = "direct"
    if "google" in ref_lower:
        source = "google"
    elif "facebook" in ref_lower or "fb.com" in ref_lower:
        source = "facebook"
    elif "instagram" in ref_lower:
        source = "instagram"
    elif "twitter" in ref_lower or "t.co" in ref_lower or "x.com" in ref_lower:
        source = "twitter"
    elif "linkedin" in ref_lower:
        source = "linkedin"
    elif "wa.me" in ref_lower or "whatsapp" in ref_lower:
        source = "whatsapp"
    elif referrer:
        source = "referral"

    # Allow ?source= override (useful for campaign tracking)
    source_override = request.GET.get("source")
    if source_override and source_override in dict(PageVisit.SOURCE_CHOICES):
        source = source_override

    PageVisit.objects.create(
        session_key=session_key,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        referrer=referrer[:500],
        source=source,
        path=request.path,
    )

    context = {
        "digital_resources": digital_resources,
        "top_downloaded_resources": top_downloaded_resources,
        "is_public_page": True,
    }
    return render(request, "digital/home.html", context)


def delete_resource(request, id):
    resource = get_object_or_404(Resource, id=id)

    if request.method == "POST":
        resource.delete()
        return redirect("admin")

    return render(request, "digital/delete.html", {"resource": resource})


def edit_resource(request, id):
    resource = get_object_or_404(Resource, id=id)

    if request.method == "POST":
        resource.title = request.POST.get("title")
        resource.description = request.POST.get("description")

        if request.FILES.get("thumbnail"):
            resource.thumbnail = request.FILES["thumbnail"]

        if request.FILES.get("file"):
            resource.file = request.FILES["file"]

        resource.save()

        return redirect("admin")

    return render(
        request,
        "digital/edit.html",
        {"resource": resource},
    )


@admin_required
def admin(request):
    from digital.models import ActivityLog, Payment, Subscription, Invoice
    from django.utils import timezone
    from datetime import timedelta

    # ---- Handle resource upload (lead magnet) ----
    if request.method == "POST":
        thumbnail = request.FILES.get("thumbnail")
        file = request.FILES.get("file")
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()

        if not title or not file:
            messages.error(request, "Title and file are required.")
        else:
            Resource.objects.create(
                thumbnail=thumbnail,
                file=file,
                title=title,
                description=description,
            )
            messages.success(request, f'Resource "{title}" uploaded successfully.')
        return redirect("admin")

    # ---- Time anchors ----
    today = timezone.now().date()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=7)

    # ---- Leads & Resources ----
    user_count = Lead.objects.count()
    total_resources = Resource.objects.count()
    total_downloads = (
        Resource.objects.aggregate(total=Sum("most_downloaded"))["total"] or 0
    )
    most_downloaded_resource = Resource.objects.order_by("-most_downloaded").first()

    # ---- Revenue ----
    total_revenue = (
        Payment.objects.filter(status="success").aggregate(total=Sum("amount"))["total"]
        or 0
    )
    monthly_revenue = (
        Payment.objects.filter(
            status="success", transaction_date__date__gte=month_start
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    premium_users = Subscription.objects.filter(
        plan__slug="premium", active=True
    ).count()
    total_payments_count = Payment.objects.filter(status="success").count()

    # ---- Users ----
    total_users = User.objects.exclude(is_superuser=True).count()
    new_users_this_week = (
        User.objects.filter(date_joined__date__gte=week_start)
        .exclude(is_superuser=True)
        .count()
    )

    # ---- Activities ----
    total_activities = ActivityLog.objects.count()
    today_activities = ActivityLog.objects.filter(created_at__date=today).count()

    # ---- Security ----
    security_events = ActivityLog.objects.filter(
        action__in=["login", "upgrade"]
    ).count()
    failed_events = ActivityLog.objects.filter(status="failed").count()

    # ---- Recent data ----
    recent_resources = Resource.objects.order_by("-created_at")[:5]
    recent_leads = Lead.objects.order_by("-created_at")[:5]
    recent_payments = Payment.objects.filter(status="success").order_by(
        "-transaction_date"
    )[:5]

    context = {
        # Leads & Resources
        "user_count": user_count,
        "total_resources": total_resources,
        "total_downloads": total_downloads,
        "most_downloaded_resource": most_downloaded_resource,
        "recent_resources": recent_resources,
        "recent_leads": recent_leads,
        # Revenue
        "total_revenue": total_revenue,
        "monthly_revenue": monthly_revenue,
        "premium_users": premium_users,
        "total_payments_count": total_payments_count,
        "recent_payments": recent_payments,
        # Users
        "total_users": total_users,
        "new_users_this_week": new_users_this_week,
        # Activities
        "total_activities": total_activities,
        "today_activities": today_activities,
        # Security
        "security_events": security_events,
        "failed_events": failed_events,
    }

    return render(request, "digital/admin.html", context)


def resource_detail(request, slug):
    resource = get_object_or_404(Resource, slug=slug)

    # Related resources (exclude current, paginated 5 per page)
    related_qs = Resource.objects.exclude(pk=resource.pk).order_by("-created_at")
    related_paginator = Paginator(related_qs, 5)
    related_page = request.GET.get("related_page")
    related_resources = related_paginator.get_page(related_page)

    # Top downloaded (sidebar-style)
    top_downloaded_resources = Resource.objects.order_by("-most_downloaded")[:5]

    context = {
        "resource": resource,
        "related_resources": related_resources,
        "top_downloaded_resources": top_downloaded_resources,
        "is_public_page": True,  # <-- Makes header/footer render even if logged in
    }
    return render(request, "digital/resource_detail.html", context)


@ratelimit(key="ip", rate="5/m", method="POST", block=False)
def create_account(request):
    # ---- Rate limit check ----
    if request.method == "POST" and getattr(request, "limited", False):
        messages.error(
            request,
            "Too many signup attempts. Please wait a minute and try again.",
        )
        return render(
            request,
            "digital/create-account.html",
            {"form": CustomUserCreationForm()},
        )

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # ---- Duplicate-email guard ----
            # If an inactive account with this email already exists and is older
            # than 1 hour, delete it so the user can re-register.
            # (Prevents permanent lockout from stale unverified signups.)
            email = form.cleaned_data.get("email", "").strip().lower()
            existing = User.objects.filter(email__iexact=email).first()
            if existing:
                if (
                    not existing.is_active
                    and existing.date_joined < timezone.now() - timedelta(hours=1)
                ):
                    existing.delete()
                else:
                    form.add_error(
                        "email", "An account with this email already exists."
                    )
                    return render(
                        request, "digital/create-account.html", {"form": form}
                    )

            # ---- Create user as INACTIVE (pending verification) ----
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            verification = EmailVerification.objects.create(user=user)

            # Dynamically build the link using the current request's host
            verification_link = request.build_absolute_uri(
                reverse("verify_email", kwargs={"token": verification.token})
            )

            # ---- Send email WITHOUT blocking the worker ----
            # On Render, outbound SMTP is blocked. fail_silently=True + try/except
            # ensures the request never crashes or kills the Gunicorn worker.
            try:
                send_mail(
                    subject="Verify your Foundry account",
                    message=f"Click the link to verify your account: {verification_link}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception as e:
                import logging

                logging.getLogger(__name__).exception(
                    "Verification email failed for %s: %s", user.email, e
                )

            return redirect("verification_sent")

        # Form invalid — re-render with errors, do NOT save anything
        return render(request, "digital/create-account.html", {"form": form})

    form = CustomUserCreationForm()
    return render(request, "digital/create-account.html", {"form": form})


@ratelimit(key="ip", rate="10/m", method="POST", block=False)
@ratelimit(key="post:username", rate="5/m", method="POST", block=False)
def login_view(request):
    # ---- Rate limit check: MUST come before any auth logic ----
    if request.method == "POST" and getattr(request, "limited", False):
        return render(
            request,
            "digital/login.html",
            {
                "error_message": (
                    "Too many login attempts. " "Please wait a minute and try again."
                ),
            },
        )

    if request.method == "POST":
        raw_username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=raw_username, password=password)

        if user is None:
            try:
                user_obj = User.objects.get(email=raw_username)
                user = authenticate(
                    request, username=user_obj.username, password=password
                )
            except User.DoesNotExist:
                pass

        if user is not None:
            login(request, user)
            log_activity(user, "login", "Logged in")

            if user.is_superuser:
                return redirect("admin")
            else:
                return redirect("user_dashboard")
        else:
            try:
                user_obj = User.objects.get(username=raw_username)
                if not user_obj.is_active:
                    messages.error(
                        request,
                        "Your account is not verified. Check your email for the verification link.",
                    )
                    return redirect("resend_verification")
            except User.DoesNotExist:
                try:
                    user_obj = User.objects.get(email=raw_username)
                    if not user_obj.is_active:
                        messages.error(
                            request,
                            "Your account is not verified. Check your email for the verification link.",
                        )
                        return redirect("resend_verification")
                except User.DoesNotExist:
                    pass

            return render(
                request,
                "digital/login.html",
                {"error_message": "Invalid username or password."},
            )

    return render(request, "digital/login.html")


def verification_sent(request):
    return render(request, "digital/verification_sent.html")


def verify_email(request, token):
    try:
        verification = EmailVerification.objects.get(token=token, used=False)
        if verification.is_expired():
            messages.error(
                request, "The verification link has expired. Please request a new one."
            )
            # Pass the email so resend_verification can find the user
            return redirect(
                f"{reverse('resend_verification')}?email={verification.user.email}"
            )
        user = verification.user
        user.is_active = True
        user.save()
        verification.used = True
        verification.save()
        messages.success(request, "Your email has been verified! You can now log in.")
        return redirect("login")
    except EmailVerification.DoesNotExist:
        messages.error(request, "Invalid verification link.")
        return redirect("login")


# @login_required
# @login_required
@ratelimit(key="ip", rate="3/m", method="GET", block=False)
def resend_verification(request):
    # ---- Rate limit check ----
    if getattr(request, "limited", False):
        messages.error(
            request,
            "Too many verification requests. Please wait a minute.",
        )
        return redirect("login")

    # Get email from query string (sent from login view)
    email = request.GET.get("email")
    if not email:
        messages.error(request, "Email is required to resend verification.")
        return redirect("login")

    # Always show the same message regardless of outcome.
    # This prevents user enumeration: an attacker cannot tell whether
    # an email is registered or not based on the response.
    success_msg = (
        "If an inactive account exists for that email, "
        "a new verification link has been sent."
    )

    try:
        user = User.objects.get(email=email, is_active=False)
        verification = user.verification

        if verification.is_expired():
            # Generate new token
            verification.token = secrets.token_urlsafe(32)
            verification.created_at = timezone.now()
            verification.save()

            # Send new email
            verification_link = request.build_absolute_uri(
                reverse("verify_email", kwargs={"token": verification.token})
            )

            # ---- Send email WITHOUT blocking the worker ----
            try:
                send_mail(
                    subject="Verify your Foundry account",
                    message=f"Click the link to verify your account: {verification_link}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception as e:
                import logging

                logging.getLogger(__name__).exception(
                    "Resend verification email failed for %s: %s", user.email, e
                )
        # If not expired, we still return the generic success message.
        # The user can check their inbox — no information leaked.

    except (User.DoesNotExist, EmailVerification.DoesNotExist):
        # Silently ignore — do NOT reveal that the email isn't registered.
        pass

    messages.success(request, success_msg)
    return redirect("verification_sent")


def logout_view(request):
    logout(request)
    return redirect("home")

# Matt24emma2024@
# Liberty24@


def leads(request, slug):
    resource = get_object_or_404(Resource, slug=slug)
    message = ""

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()

        if not name or not email or not phone:
            message = "All fields are required."

        elif len(name) < 2 or len(name) > 100:
            message = "Enter a valid name."

        else:
            try:
                validate_email(email)
            except ValidationError:
                message = "Enter a valid email address."

            else:
                if not re.fullmatch(r"^[0-9+\-\s()]{7,20}$", phone):
                    message = "Enter a valid phone number."

                else:
                    # Get existing lead or create a new one
                    lead, created = Lead.objects.get_or_create(
                        email=email,
                        defaults={
                            "name": name,
                            "phone": phone,
                        },
                    )

                    # If the lead already exists, optionally update their details
                    if not created:
                        lead.name = name
                        lead.phone = phone
                        lead.save()

                    # Store session data
                    request.session["lead_verified"] = True
                    request.session["lead_id"] = lead.id

                    return redirect("download_resource", slug=resource.slug)

    return render(
        request,
        "digital/leads.html",
        {
            "message": message,
            "resource": resource,
            "is_public_page": True,  # <-- ensures marketing layout for everyone
        },
    )


def reset_session(request):
    request.session.flush()
    return redirect("home")


@admin_required
def export_leads_pdf(request):
    from django.db.models import Count
    from django.utils import timezone
    from datetime import timedelta

    period = request.GET.get("period", "today")
    today = timezone.now().date()

    if period == "today":
        start = today
        period_label = "Today"
    elif period == "week":
        start = today - timedelta(days=7)
        period_label = "Last 7 Days"
    elif period == "month":
        start = today.replace(day=1)
        period_label = "This Month"
    else:
        start = None
        period_label = "All Time"

    leads = (
        Lead.objects.prefetch_related("downloads__resource")
        .annotate(number_of_resources_downloaded=Count("downloads", distinct=True))
        .order_by("-created_at")
    )
    if start:
        leads = leads.filter(created_at__date__gte=start)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#0F172A"),
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748B"),
    )

    elements = [
        Paragraph("Foundry Leads Report", title_style),
        Paragraph(
            f"Period: {period_label} · Generated {timezone.now().strftime('%b %d, %Y %H:%M')}",
            sub_style,
        ),
        Spacer(1, 20),
    ]

    data = [["Name", "Email", "Files", "Count", "Joined"]]
    for lead in leads:
        files = ", ".join([d.resource.title for d in lead.downloads.all()]) or "—"
        data.append(
            [
                lead.name,
                lead.email,
                files[:60],
                str(lead.number_of_resources_downloaded),
                lead.created_at.strftime("%b %d, %Y"),
            ]
        )

    if len(data) == 1:
        data.append(["No leads found", "—", "—", "—", "—"])

    table = Table(
        data, colWidths=[1.2 * inch, 1.8 * inch, 2 * inch, 0.6 * inch, 1 * inch]
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8FAFC")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="foundry_leads_{period}.pdf"'
    )
    return response


@admin_required
def downloads(request):
    today = timezone.now().date()
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)

    period = request.GET.get("period", "today")
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = week_start
    elif period == "month":
        start_date = month_start
    else:
        start_date = None

    # ---- Leads with downloads ----
    leads_qs = (
        Lead.objects.prefetch_related("downloads__resource")
        .annotate(
            number_of_resources_downloaded=Count("downloads", distinct=True),
            visit_count=Count("visits", distinct=True),
        )
        .order_by("-created_at")
    )

    # ---- Visitor metrics (PageVisit-based) ----
    if start_date:
        period_visits = PageVisit.objects.filter(visited_at__date__gte=start_date)
        unique_visitors = period_visits.values("session_key").distinct().count()

        period_sessions = period_visits.values_list("session_key", flat=True)
        returning_visitors = (
            PageVisit.objects.filter(
                session_key__in=period_sessions,
                visited_at__date__lt=start_date,
            )
            .values("session_key")
            .distinct()
            .count()
        )

        downloads_period = Download.objects.filter(downloaded_at__date__gte=start_date)
    else:
        unique_visitors = PageVisit.objects.values("session_key").distinct().count()
        returning_visitors = (
            PageVisit.objects.values("session_key")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .count()
        )
        downloads_period = Download.objects.all()

    total_downloads = downloads_period.count()

    # ---- Traffic sources (from PageVisit) ----
    if start_date:
        source_qs = (
            PageVisit.objects.filter(visited_at__date__gte=start_date)
            .values("source")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
    else:
        source_qs = (
            PageVisit.objects.values("source")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

    source_labels = dict(PageVisit.SOURCE_CHOICES)
    traffic_sources = [
        {"label": source_labels.get(s["source"], s["source"]), "count": s["count"]}
        for s in source_qs
    ]

    # Pagination
    paginator = Paginator(leads_qs, 15)
    page_number = request.GET.get("page")
    leads = paginator.get_page(page_number)

    resources = Resource.objects.order_by("-created_at")

    context = {
        "leads": leads,
        "resources": resources,
        "period": period,
        "unique_visitors": unique_visitors,
        "returning_visitors": returning_visitors,
        "total_downloads": total_downloads,
        "total_leads": Lead.objects.count(),
        "traffic_sources": traffic_sources,
    }
    return render(request, "digital/downloads.html", context)


@login_required
def summary(request):
    user = request.user
    # Base queryset
    summaries_list = (
        ChapterSummary.objects.filter(book__user=user)
        .select_related("book", "category")
        .order_by("-created_at")
    )

    # Type filter: 'ideas' = no book (personal ideas), 'books' = has book
    type_filter = request.GET.get("type")
    if type_filter == "ideas":
        summaries_list = summaries_list.filter(book__isnull=True)
    elif type_filter == "books":
        summaries_list = summaries_list.filter(book__isnull=False)

    # Category filter
    category_id = request.GET.get("category")
    if category_id:
        summaries_list = summaries_list.filter(category_id=category_id)

    categories = Category.objects.filter(user=user)
    paginator = Paginator(summaries_list, 10)
    page_number = request.GET.get("page")
    summaries = paginator.get_page(page_number)

    context = {
        "summaries": summaries,
        "categories": categories,
        "selected_category": int(category_id) if category_id else None,
        "current_type": type_filter or "all",
    }
    return render(request, "digital/dashboard/summaries_list.html", context)


@login_required
def summaryForm(request):
    categories = Category.objects.filter(user=request.user)
    book_id = request.GET.get("book_id")

    # Correctly get premium status
    subscription, _ = Subscription.objects.get_or_create(user=request.user)
    is_premium = subscription.is_premium()

    if request.method == "POST":
        form = ChapterSummaryForm(request.POST)
        if form.is_valid():
            book_title = request.POST.get("book_title", "").strip()
            author = request.POST.get("author", "").strip()

            book = None
            if book_title:
                book, created = Book.objects.get_or_create(
                    user=request.user, title=book_title, defaults={"author": author}
                )
                if created:
                    log_activity(
                        request.user, "upload_book", f"Uploaded book: {book.title}"
                    )

            summary = form.save(commit=False)
            summary.user = request.user
            summary.book = book
            summary.save()

            log_activity(
                request.user,
                "create_summary",
                f"Created summary for {summary.book.title if summary.book else 'personal idea'}",
            )
            return redirect("review", pk=summary.pk)

        # If form is invalid, re-render with errors
        return render(
            request,
            "digital/summaryForm.html",
            {
                "form": form,
                "categories": categories,
                "book_title": request.POST.get("book_title", ""),
                "author": request.POST.get("author", ""),
                "is_premium": is_premium,
            },
        )

    # GET request logic (initial data)
    initial = {}
    if book_id and book_id != "all":
        try:
            book = Book.objects.get(id=book_id, user=request.user)
            initial["book_title"] = book.title
            initial["author"] = book.author
        except Book.DoesNotExist:
            pass

    form = ChapterSummaryForm(initial=initial)
    return render(
        request,
        "digital/summaryForm.html",
        {
            "form": form,
            "categories": categories,
            "book_title": initial.get("book_title", ""),
            "author": initial.get("author", ""),
            "book_id": book_id,
            "is_premium": is_premium,
        },
    )


@login_required
def edit_summary(request, pk):
    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)
    categories = Category.objects.filter(user=request.user)

    if request.method == "POST":
        form = ChapterSummaryForm(request.POST, instance=summary)
        if form.is_valid():
            # Optionally update book title/author if needed
            book_title = request.POST.get("book_title")
            author = request.POST.get("author", "")
            if book_title:
                summary.book.title = book_title
                summary.book.author = author
                summary.book.save()
            form.save()
            return redirect("review", pk=summary.pk)
    else:
        form = ChapterSummaryForm(instance=summary)

    return render(
        request,
        "digital/summaryForm.html",
        {
            "form": form,
            "categories": categories,
            "editing": True,
            "summary_id": summary.pk,
            "book_title": summary.book.title,
            "author": summary.book.author,
        },
    )


@login_required
def export_summary_pdf(request, pk):
    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)

    # Check premium
    subscription, _ = Subscription.objects.get_or_create(user=request.user)
    if not subscription.is_premium():
        messages.error(
            request, "Export to PDF is a premium feature. Please upgrade to premium."
        )
        return redirect("pricing")

    # Log activity only after premium check passes
    log_activity(
        request.user, "export_pdf", f"Exported summary: {summary.chapter_title}"
    )
    return generate_summary_pdf(
        summary, title=f"{summary.book.title} - {summary.chapter_title}"
    )


@login_required
def export_category_pdf(request, category_id):
    category = get_object_or_404(Category, pk=category_id, user=request.user)

    # Check premium
    subscription, _ = Subscription.objects.get_or_create(user=request.user)
    if not subscription.is_premium():
        messages.error(
            request, "Export to PDF is a premium feature. Please upgrade to premium."
        )
        return redirect("pricing")

    summaries = category.summaries.filter(book__user=request.user).order_by(
        "-created_at"
    )
    if not summaries.exists():
        messages.error(request, "No summaries in this category to export.")
        return redirect("manage_categories")

    # Log activity only after premium check passes and summaries exist
    log_activity(request.user, "export_pdf", f"Exported category: {category.name}")
    return generate_category_summary_pdf(summaries, category.name)


@login_required
def delete_summary(request, pk):
    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)
    if request.method == "POST":
        summary.delete()
        messages.success(request, "Summary deleted successfully.")
        return redirect("all_summaries")
    return render(request, "digital/delete_summary.html", {"summary": summary})


# Review summary
@login_required
def review(request, pk):

    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)

    return render(request, "digital/review.html", {"summary": summary})


# digital/views.py


@login_required
def generate_cards(request, pk):
    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)
    if summary.card_image:
        messages.info(request, "This card has already been generated.")
        return redirect("summary")

    # Check generation limit
    generation, _ = UserCardGeneration.objects.get_or_create(user=request.user)
    subscription, _ = Subscription.objects.get_or_create(user=request.user)
    if not subscription.is_premium() and not generation.can_generate():
        messages.error(
            request, "You have reached your daily card generation limit (3)."
        )
        return redirect("summary")

    # Get preferences from session, or set defaults
    prefs = request.session.get("card_preferences", {})
    context = {
        "summary": summary,
        "card_color": prefs.get("color", "sticker-white"),
        "font_family": prefs.get("font", "Inter"),
        "font_color": prefs.get("font_color", "#0F172A"),  # text-primary
    }
    return render(request, "digital/cards.html", context)


@login_required
def save_card_image(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)
    if summary.card_image:
        return JsonResponse({"error": "Card already exists"}, status=400)

    # Check limit again
    generation, _ = UserCardGeneration.objects.get_or_create(user=request.user)
    subscription, _ = Subscription.objects.get_or_create(user=request.user)
    if not subscription.is_premium() and not generation.can_generate():
        return JsonResponse({"error": "Generation limit reached"}, status=403)

    image_data = request.POST.get("image")
    if not image_data:
        return JsonResponse({"error": "No image data"}, status=400)

    # Save preferences from POST to session
    prefs = {
        "color": request.POST.get("color", "sticker-white"),
        "font": request.POST.get("font", "Inter"),
        "font_color": request.POST.get("font_color", "#0F172A"),
    }
    request.session["card_preferences"] = prefs

    # Decode and save image
    try:
        format, imgstr = image_data.split(";base64,")
        ext = format.split("/")[-1]
        image = ContentFile(base64.b64decode(imgstr), name=f"card_{summary.pk}.{ext}")
    except Exception:
        return JsonResponse({"error": "Invalid image data"}, status=400)

    summary.card_image = image
    summary.card_generated_at = timezone.now()
    summary.save()

    generation.increment()

    return JsonResponse({"success": True, "redirect_url": reverse("summary")})


@login_required
def save_card_image(request, pk):
    """Receive the captured PNG, save to summary, increment generation count."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)
    if summary.card_image:
        return JsonResponse({"error": "Card already exists"}, status=400)

    # Check limit again
    generation, _ = UserCardGeneration.objects.get_or_create(user=request.user)
    subscription, _ = Subscription.objects.get_or_create(user=request.user)
    if not subscription.is_premium() and not generation.can_generate():
        return JsonResponse({"error": "Generation limit reached"}, status=403)

    image_data = request.POST.get("image")
    if not image_data:
        return JsonResponse({"error": "No image data"}, status=400)

    # Decode base64 image (data:image/png;base64,....)
    try:
        format, imgstr = image_data.split(";base64,")
        ext = format.split("/")[-1]
        image = ContentFile(base64.b64decode(imgstr), name=f"card_{summary.pk}.{ext}")
    except Exception:
        return JsonResponse({"error": "Invalid image data"}, status=400)

    summary.card_image = image
    summary.card_generated_at = timezone.now()
    summary.save()

    log_activity(
        request.user,
        "generate_cards",
        f"Generated a knowledge card for {summary.book.title}",
    )
    
    generation.increment()
    return JsonResponse({"success": True, "redirect_url": reverse("summary")})


@login_required
def download_card_png(request, pk):
    """Serve the PNG for download, enforce download limit (5/day for free)."""
    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)
    if not summary.card_image:
        return JsonResponse({"error": "Card not found"}, status=404)

    # Check download limit (free users: 5 per day)
    user = request.user
    subscription, _ = Subscription.objects.get_or_create(user=user)
    if not subscription.is_premium():
        usage, _ = DownloadUsage.objects.get_or_create(
            user=user,
            defaults={"month": timezone.now().month, "year": timezone.now().year},
        )
        today = timezone.now()
        if usage.month != today.month or usage.year != today.year:
            usage.downloads_this_month = 0
            usage.month = today.month
            usage.year = today.year
            usage.save()
        if usage.downloads_this_month >= 5:
            return JsonResponse(
                {"error": "Download limit reached (5 per day). Upgrade to premium."},
                status=403,
            )
        usage.downloads_this_month += 1
        usage.save()

    # Serve the image
    response = HttpResponse(summary.card_image.read(), content_type="image/png")
    response["Content-Disposition"] = (
        f'attachment; filename="knowledge_card_{summary.pk}.png"'
    )
    log_activity(
        request.user, "download_resource", f"Downloaded knowledge card for {summary.book.title}"
    )
    return response
    return response

@admin_required
def recent_cards(request):
    cards = ChapterSummary.objects.filter(card_image__isnull=False).order_by('-card_generated_at')
    paginator = Paginator(cards, 5)
    page = request.GET.get('page')
    cards_page = paginator.get_page(page)
    return render(request, 'digital/recent_cards.html', {'cards': cards_page})


@login_required
def download_card(request, pk):

    if request.method != "POST":
        return JsonResponse({"error": "POST request required."}, status=405)

    summary = get_object_or_404(ChapterSummary, pk=pk, book__user=request.user)

    today = timezone.now()

    subscription, created = Subscription.objects.get_or_create(user=request.user)

    usage, created = DownloadUsage.objects.get_or_create(
        user=request.user,
        defaults={
            "month": today.month,
            "year": today.year,
        },
    )

    # Reset every new month
    if usage.month != today.month or usage.year != today.year:

        usage.downloads_this_month = 0
        usage.month = today.month
        usage.year = today.year

        usage.save()

    # Premium users have unlimited downloads
    if subscription.is_premium():
        log_activity(
            request.user,
            "download_resource",
            f"Downloaded knowledge card for {summary.book.title}",
        )
        return JsonResponse(
            {
                "allowed": True,
                "downloads_used": usage.downloads_this_month,
                "unlimited": True,
            }
        )

    # Free limit reached
    FREE_LIMIT = 5

    if usage.downloads_this_month >= FREE_LIMIT:

        return JsonResponse(
            {
                "allowed": False,
                "downloads_used": usage.downloads_this_month,
                "limit": FREE_LIMIT,
                "upgrade_required": True,
            }
        )

    # Consume one download
    usage.downloads_this_month += 1
    usage.save()

    log_activity(
        request.user,
        "download_resource",
        f"Downloaded knowledge card for {summary.book.title}",
    )
    return JsonResponse(
        {
            "allowed": True,
            "downloads_used": usage.downloads_this_month,
            "limit": FREE_LIMIT,
            "unlimited": False,
        }
    )


def pricing(request):
    return render(request, "digital/pricing.html",{"is_public_page": True,})


@ratelimit(key="user", rate="10/m", method="POST", block=False)
@login_required
def initialize_payment(request):
    """
    Initialize a Paystack transaction for ₦100 (test price during launch phase).
    Creates a pending Payment record so we can track the attempt.
    """
    # ---- Rate limit check ----
    if request.method == "POST" and getattr(request, "limited", False):
        messages.error(
            request,
            "Too many payment attempts. Please wait a minute.",
        )
        return redirect("pricing")

    # Prevent double-initiation if already on a paid plan
    subscription, _ = Subscription.objects.get_or_create(user=request.user)
    if subscription.is_premium():
        messages.info(request, "You're already on Premium.")
        return redirect("pricing")

    # Generate a unique reference (Paystack requires this to be unique per attempt)
    reference = f"foundry_{request.user.id}_{uuid.uuid4().hex[:12]}"

    # Amount is in kobo (1 Naira = 100 kobo). ₦100 = 10,000 kobo.
    amount_kobo = 100 * 100
    currency = "NGN"

    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "email": request.user.email,
        "amount": amount_kobo,
        "currency": currency,
        "reference": reference,
        "callback_url": request.build_absolute_uri(reverse("payment_callback")),
        "metadata": {
            "user_id": request.user.id,
            "username": request.user.username,
            "plan": "premium",
            "initiated_at": timezone.now().isoformat(),
        },
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
        result = response.json()
    except requests.RequestException as e:
        messages.error(request, f"Payment gateway unreachable: {str(e)}")
        return redirect("pricing")

    if result.get("status") is True and result.get("data", {}).get("authorization_url"):
        auth_url = result["data"]["authorization_url"]
        returned_reference = result["data"]["reference"]

        # Create a pending Payment record (tracked in admin payments page)
        Payment.objects.create(
            user=request.user,
            amount=100.00,  # ₦100.00
            currency="NGN",
            reference=returned_reference,
            status="pending",
            metadata={
                "email": request.user.email,
                "plan": "premium",
                "initiated_at": timezone.now().isoformat(),
            },
        )

        # Log authorization event
        PaymentEvent.objects.create(
            user=request.user,
            event_type="authorization",
            amount=100.00,
            metadata={"reference": returned_reference},
        )

        return redirect(auth_url)

    # Paystack returned an error
    error_msg = result.get("message", "Unable to initialize payment.")
    messages.error(request, error_msg)
    return redirect("pricing")


@login_required
def payment_callback(request):
    """
    Verify the transaction with Paystack after redirect.
    Idempotent: safe to hit multiple times for the same reference.
    """
    reference = request.GET.get("reference")
    if not reference:
        messages.error(request, "Missing payment reference.")
        return redirect("pricing")

    # If this reference is already recorded as successful, just redirect
    if Payment.objects.filter(reference=reference, status="success").exists():
        messages.success(request, "Payment already confirmed.")
        return redirect("user_dashboard")

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }
    verify_url = f"https://api.paystack.co/transaction/verify/{reference}"

    try:
        response = requests.get(verify_url, headers=headers, timeout=15)
        result = response.json()
    except requests.RequestException as e:
        messages.error(request, f"Could not verify payment: {str(e)}")
        return redirect("pricing")

    if not result.get("status"):
        messages.error(request, "Payment verification failed.")
        return redirect("pricing")

    transaction = result.get("data", {})
    if transaction.get("status") != "success":
        # Mark any pending record as failed
        Payment.objects.filter(reference=reference).update(
            status="failed",
            failure_reason=transaction.get(
                "gateway_response", "Payment was not successful."
            ),
        )
        PaymentEvent.objects.create(
            user=request.user,
            event_type="failure",
            amount=transaction.get("amount", 0) / 100,
            metadata={
                "reference": reference,
                "reason": transaction.get("gateway_response", ""),
            },
        )
        log_activity(request.user, "payment_failed", f"Payment failed: {reference}")
        messages.error(request, "Payment was not successful.")
        return redirect("pricing")

    # ---- Success path ----
    payment = Payment.objects.filter(reference=reference).first()
    if not payment:
        # Recovery case: create it now with the verified amount
        payment = Payment.objects.create(
            user=request.user,
            amount=transaction["amount"] / 100,
            currency=transaction.get("currency", "NGN"),
            reference=reference,
            status="success",
            transaction_date=timezone.now(),
            metadata={"recovered": True},
        )
    else:
        payment.status = "success"
        payment.amount = transaction["amount"] / 100
        payment.currency = transaction.get("currency", "NGN")
        payment.transaction_date = timezone.now()
        payment.save()

    # Get or create Premium plan
    premium_plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={"name": "Premium", "monthly_price": 100.00, "currency": "NGN"},
    )

    # Activate or extend the subscription
    subscription, _ = Subscription.objects.get_or_create(user=request.user)
    subscription.plan = premium_plan
    subscription.status = "active"
    subscription.active = True
    subscription.paystack_customer_code = transaction.get("customer", {}).get(
        "customer_code", ""
    )

    now = timezone.now()
    if subscription.current_period_end and subscription.current_period_end > now:
        subscription.current_period_end = subscription.current_period_end + timedelta(
            days=30
        )
    else:
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=30)
    subscription.save()

    # Create an invoice
    invoice_number = f"INV-{reference}"
    invoice, created = Invoice.objects.get_or_create(
        invoice_number=invoice_number,
        user=request.user,
        defaults={
            "subscription": subscription,
            "payment": payment,
            "amount": payment.amount,
            "currency": payment.currency,
            "issue_date": now,
            "due_date": now + timedelta(days=7),
            "paid_date": now,
            "status": "paid",
        },
    )

    # Log events
    PaymentEvent.objects.create(
        user=request.user,
        event_type="capture",
        amount=payment.amount,
        metadata={"reference": reference},
    )
    PaymentEvent.objects.create(
        user=request.user,
        event_type="subscription_created",
        amount=payment.amount,
        metadata={"plan": "premium", "subscription_id": subscription.id},
    )
    if created:
        PaymentEvent.objects.create(
            user=request.user,
            event_type="invoice_generated",
            amount=payment.amount,
            metadata={"invoice_number": invoice.invoice_number},
        )

    log_activity(request.user, "upgrade", "Upgraded to Premium (₦100)")
    messages.success(request, "Welcome to Premium! 🎉")

    return redirect("user_dashboard")


@login_required
def user_dashboard(request):
    user = request.user

    # Summaries (latest 5)
    summaries = (
        ChapterSummary.objects.filter(book__user=user)
        .select_related("book")
        .order_by("-created_at")[:5]
    )

    # Subscription and download usage
    subscription, _ = Subscription.objects.get_or_create(user=user)
    usage, _ = DownloadUsage.objects.get_or_create(
        user=user,
        defaults={"month": timezone.now().month, "year": timezone.now().year},
    )

    # Statistics
    total_books = Book.objects.filter(user=user).count()
    total_summaries = ChapterSummary.objects.filter(book__user=user).count()
    total_cards = total_summaries * 8  # placeholder
    downloads_used = usage.downloads_this_month
    is_premium = subscription.is_premium()

    # Recent books (with chapter count via annotation)
    recent_books = (
        Book.objects.filter(user=user)
        .annotate(chapter_count=Count("chapters"))
        .order_by("-created_at")[:5]
    )
    # Add total_chunks and progress (placeholders)
    for book in recent_books:
        book.total_chunks = book.chunks.count()
        book.progress = 0

    # Active book (the most recent book that has chunks)
    active_book = (
        Book.objects.filter(user=user, chunks__isnull=False)
        .order_by("-created_at")
        .first()
    )
    reading_progress = 0
    if active_book:
        total_chunks = active_book.chunks.count()
        # For now, progress = 0; we'll later compute from delivered chunks
        reading_progress = 0

    # Recent activity (latest 5)
    activities = ActivityLog.objects.filter(user=user).order_by("-created_at")[:5]

    context = {
        "recent_summaries": summaries,
        "recent_books": recent_books,
        "total_books": total_books,
        "total_summaries": total_summaries,
        "total_cards": total_cards,
        "downloads_used": downloads_used,
        "download_percentage": (
            min(downloads_used / 5 * 100, 100) if not is_premium else 100
        ),
        "is_premium": is_premium,
        "user_name": user.get_full_name() or user.username,
        "active_book": active_book,
        "reading_progress": reading_progress,
        "activities": activities,
    }
    return render(request, "digital/dashboard/user_dashboard.html", context)


from django.db.models import Count


@login_required
def library(request):
    # Books: only those with file and chunks
    books_list = (
        Book.objects.filter(user=request.user, file__isnull=False)
        .annotate(chunk_count=Count("chunks"))
        .filter(chunk_count__gt=0)
        .order_by("-created_at")
    )

    # Compute progress for each book
    for book in books_list:
        total_chunks = book.chunks.count()
        read_chunks = book.chunks.filter(is_read=True).count()
        book.progress = (
            int((read_chunks / total_chunks * 100)) if total_chunks > 0 else 0
        )

    book_paginator = Paginator(books_list, 12)
    book_page = request.GET.get("page")
    books = book_paginator.get_page(book_page)

    # Summary cards: generated PNGs
    summaries_list = (
        ChapterSummary.objects.filter(book__user=request.user, card_image__isnull=False)
        .select_related("book", "category")
        .order_by("-card_generated_at")
    )

    card_paginator = Paginator(summaries_list, 12)
    card_page = request.GET.get("card_page")
    summaries = card_paginator.get_page(card_page)

    context = {
        "books": books,
        "summaries": summaries,
    }
    return render(request, "digital/dashboard/library.html", context)


@login_required
def delete_scheduled_book(request, book_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    book = get_object_or_404(Book, id=book_id, user=request.user)
    book.delete()
    return JsonResponse({"success": True})


@login_required
def reading_session(request):
    return render(request, "digital/dashboard/reading-session.html")


@login_required
def update_pages_per_day(request, book_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    book = get_object_or_404(Book, id=book_id, user=request.user)
    pages = request.POST.get("pages_per_day")
    if pages:
        try:
            book.pages_per_day = int(pages)
            book.save()
            return JsonResponse({"success": True})
        except ValueError:
            return JsonResponse({"error": "Invalid number"}, status=400)
    return JsonResponse({"error": "Missing pages_per_day"}, status=400)


@login_required
def book_details(request):
    book_id = request.GET.get("book_id")
    if not book_id:
        return redirect("reading_plans")
    book = get_object_or_404(Book, id=book_id, user=request.user)
    chunks = book.chunks.all().order_by("chunk_number")
    summaries = book.chapters.all().order_by("-created_at")
    context = {
        "book": book,
        "chunks": chunks,
        "summaries": summaries,
    }
    return render(request, "digital/dashboard/book_details.html", context)


@login_required
def chapter_summary(request):
    return render(request, "digital/dashboard/chapter-summary.html")

@login_required
def card_manager(request):
    return render(request, "digital/dashboard/card-manager.html")


@login_required
def pdf_export(request):
    # Removed undefined 'summary' variable. Logs a generic export action.
    log_activity(request.user, "export_pdf", "Exported PDF")
    return render(request, "digital/dashboard/pdf-export.html")


@login_required
def payment_billing(request):
    user = request.user
    # Ensure subscription exists
    subscription, _ = Subscription.objects.get_or_create(user=user)
    is_premium = subscription.is_premium()
    usage, _ = DownloadUsage.objects.get_or_create(
        user=user, defaults={"month": timezone.now().month, "year": timezone.now().year}
    )

    # Usage data
    total_books = Book.objects.filter(user=user).count()
    total_summaries = ChapterSummary.objects.filter(book__user=user).count()
    total_cards = ChapterSummary.objects.filter(
        book__user=user, card_image__isnull=False
    ).count()
    downloads_used = usage.downloads_this_month
    # If you have a storage or AI usage model, fetch it here; otherwise set defaults
    storage_used_mb = 0
    ai_requests = 0

    # Determine plan details
    if is_premium and subscription.plan:
        plan_name = subscription.plan.name
        plan_price = f"₦{subscription.plan.monthly_price:,.0f}"  # e.g., ₦3,000
        plan_period = "/ month"
        plan_status = subscription.status.capitalize()
        renewal_date = subscription.current_period_end.strftime("%b %d, %Y") if subscription.current_period_end else "N/A"
    else:
        plan_name = "Free Plan"
        plan_price = "₦0"
        plan_period = "forever"
        plan_status = "Active"
        renewal_date = "N/A"

    # Billing history from real invoices
    billing_history = Invoice.objects.filter(user=user).order_by("-issue_date")[:10]
    context = {
        "is_premium": is_premium,
        "subscription": subscription,
        "plan_name": plan_name,
        "plan_price": plan_price,
        "plan_period": plan_period,
        "plan_status": plan_status,
        "renewal_date": renewal_date,
        "total_books": total_books,
        "total_summaries": total_summaries,
        "total_cards": total_cards,
        "downloads_used": downloads_used,
        "storage_used_mb": storage_used_mb,
        "ai_requests": ai_requests,
        "billing_history": billing_history,
    }
    return render(request, "digital/dashboard/payment-billing.html", context)


@login_required
def profile(request):
    user = request.user
    # Ensure profile exists
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Handle profile updates (POST)
    if request.method == "POST":
        # Handle photo upload
        if "profile_pic" in request.FILES:
            profile.avatar = request.FILES["profile_pic"]
            profile.save()
            log_activity(user, "update_profile", "Updated profile picture")
            messages.success(request, "Profile picture updated!")
            return redirect("profile")

        # Regular profile update (name, email, bio)
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        bio = request.POST.get("about", "").strip()

        changes = []
        if first_name and first_name != user.first_name:
            user.first_name = first_name
            changes.append("first name")
        if last_name and last_name != user.last_name:
            user.last_name = last_name
            changes.append("last name")
        if email and email != user.email:
            # Check if email is already used by another account
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(
                    request, "This email is already in use by another account."
                )
                return redirect("profile")
            user.email = email
            changes.append("email")
        if bio and bio != profile.bio:
            profile.bio = bio
            profile.save()
            changes.append("bio")

        if changes:
            user.save()
            log_activity(user, "update_profile", f"Updated: {', '.join(changes)}")
            messages.success(request, "Profile updated successfully!")
        else:
            messages.info(request, "No changes detected.")
        return redirect("profile")

    # Subscription & Usage
    subscription, _ = Subscription.objects.get_or_create(user=user)
    is_premium = subscription.is_premium()
    usage, _ = DownloadUsage.objects.get_or_create(
        user=user, defaults={"month": timezone.now().month, "year": timezone.now().year}
    )

    # Profile completion logic
    profile_items = {
        "photo": bool(profile.avatar),
        "personal_info": bool(user.first_name and user.last_name),
        "professional_profile": bool(profile.profession),
        "about_you": bool(profile.bio),
        "email_verified": bool(
            user.email
            and (user.email_verified if hasattr(user, "email_verified") else True)
        ),
    }
    completion_pct = sum(profile_items.values()) / len(profile_items) * 100

    # Activity Data
    activities = ActivityLog.objects.filter(user=user).order_by("-created_at")[:10]
    total_activities = ActivityLog.objects.filter(user=user).count()
    security_activities = ActivityLog.objects.filter(
        user=user, action__in=["login", "upgrade"]
    ).order_by("-created_at")[:5]

    # Book & Summary stats
    total_books = Book.objects.filter(user=user).count()
    total_summaries = ChapterSummary.objects.filter(book__user=user).count()
    total_cards = ChapterSummary.objects.filter(
        book__user=user, card_image__isnull=False
    ).count()

    # Security info
    password_last_changed = user.last_login if user.last_login else None
    has_2fa = bool(getattr(user, "two_factor_enabled", False))
    email_verified = bool(user.email)

    context = {
        "user": user,
        "is_premium": is_premium,
        "subscription": subscription,
        "usage": usage,
        "profile_items": profile_items,
        "completion_pct": int(completion_pct),
        "activities": activities,
        "total_activities": total_activities,
        "security_activities": security_activities,
        "total_books": total_books,
        "total_summaries": total_summaries,
        "total_cards": total_cards,
        "password_last_changed": password_last_changed,
        "has_2fa": has_2fa,
        "email_verified": email_verified,
        "prefs": getattr(user, "preferences", None),
        "user_bio": profile.bio,  # Use profile.bio
        "profile_pic_url": profile.avatar.url if profile.avatar else None,
    }
    return render(request, "digital/dashboard/profile.html", context)


@login_required
@require_POST
def delete_account(request):
    user = request.user
    log_activity(user, "delete_account", "Account deleted")
    user.delete()
    logout(request)
    messages.success(request, "Your account has been permanently deleted.")
    return redirect("home")


@login_required
def setting (request):
    return render(request, "digital/dashboard/settings.html")


@admin_required
def activity_admin(request):
    from digital.models import ActivityLog
    from django.utils import timezone

    today = timezone.now().date()

    # Metrics
    total_activities = ActivityLog.objects.count()
    today_count = ActivityLog.objects.filter(created_at__date=today).count()
    security_count = ActivityLog.objects.filter(action__in=["login", "upgrade"]).count()
    failed_count = ActivityLog.objects.filter(status="failed").count()
    admin_actions_count = ActivityLog.objects.filter(action__icontains="admin").count()

    # Security Alerts (Real Data)
    security_alerts = {
        "today_security": ActivityLog.objects.filter(
            action__in=["login", "upgrade"], created_at__date=today
        ).count(),
        "failed_logins": ActivityLog.objects.filter(
            action="login", status="failed"
        ).count(),
        "warnings": ActivityLog.objects.filter(status="warning").count(),
        "critical": ActivityLog.objects.filter(status="failed").count(),
    }

    # Table Data (Latest 50)
    activities = ActivityLog.objects.select_related("user", "book", "summary").order_by(
        "-created_at"
    )[:50]

    context = {
        "total_activities": total_activities,
        "today_count": today_count,
        "security_count": security_count,
        "admin_actions_count": admin_actions_count,
        "failed_count": failed_count,
        "security_alerts": security_alerts,
        "activities": activities,
    }
    return render(request, "digital/dashboard/activity-admin.html", context)


@login_required
def activity(request):
    # Base queryset
    base_qs = (
        ActivityLog.objects.filter(user=request.user)
        .select_related("book", "summary")
        .order_by("-created_at")
    )

    # Extract filters from GET
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "all")
    date = request.GET.get("date", "all")
    status = request.GET.get("status", "all")

    # Search
    if q:
        base_qs = base_qs.filter(description__icontains=q) | base_qs.filter(
            action__icontains=q
        )

    # Category filter (action)
    if category != "all":
        base_qs = base_qs.filter(action=category)

    # Date filter
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if date == "today":
        base_qs = base_qs.filter(created_at__gte=today_start)
    elif date == "7d":
        base_qs = base_qs.filter(created_at__gte=today_start - timedelta(days=7))
    elif date == "30d":
        base_qs = base_qs.filter(created_at__gte=today_start - timedelta(days=30))
    elif date == "90d":
        base_qs = base_qs.filter(created_at__gte=today_start - timedelta(days=90))

    # Status filter
    if status != "all":
        base_qs = base_qs.filter(status=status)

    # Pagination
    paginator = Paginator(base_qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Overview statistics
    total_activities = ActivityLog.objects.filter(user=request.user).count()
    today_count = ActivityLog.objects.filter(
        user=request.user, created_at__gte=today_start
    ).count()
    week_start = today_start - timedelta(days=7)
    week_count = ActivityLog.objects.filter(
        user=request.user, created_at__gte=week_start
    ).count()
    security_count = ActivityLog.objects.filter(
        user=request.user, action__in=["login", "upgrade"]
    ).count()

    # Security activities (last 5 login/upgrade actions)
    security_activities = ActivityLog.objects.filter(
        user=request.user, action__in=["login", "upgrade"]
    ).order_by("-created_at")[:5]

    context = {
        "activities": page_obj,
        "page_obj": page_obj,
        "total_activities": total_activities,
        "today_count": today_count,
        "week_count": week_count,
        "security_count": security_count,
        "security_activities": security_activities,
        "selected_category": category,
        "selected_date": date,
        "selected_status": status,
        "search_query": q,
    }
    return render(request, "digital/activity-user.html", context)


@login_required
def activity_detail(request, pk):
    activity = get_object_or_404(ActivityLog, pk=pk, user=request.user)
    data = {
        "id": activity.pk,
        "action": activity.get_action_display(),
        "description": activity.description,
        "status": activity.get_status_display(),
        "created_at": activity.created_at.isoformat(),
        "category": activity.action,
    }
    return JsonResponse(data)


@login_required
def export_activity(request):
    # Base queryset (same filters as activity view)
    base_qs = (
        ActivityLog.objects.filter(user=request.user)
        .select_related("book", "summary")
        .order_by("-created_at")
    )

    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "all")
    date = request.GET.get("date", "all")
    status = request.GET.get("status", "all")

    if q:
        base_qs = base_qs.filter(description__icontains=q) | base_qs.filter(
            action__icontains=q
        )
    if category != "all":
        base_qs = base_qs.filter(action=category)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if date == "today":
        base_qs = base_qs.filter(created_at__gte=today_start)
    elif date == "7d":
        base_qs = base_qs.filter(created_at__gte=today_start - timedelta(days=7))
    elif date == "30d":
        base_qs = base_qs.filter(created_at__gte=today_start - timedelta(days=30))
    elif date == "90d":
        base_qs = base_qs.filter(created_at__gte=today_start - timedelta(days=90))
    if status != "all":
        base_qs = base_qs.filter(status=status)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="foundry_activity.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Activity", "Description", "Status", "Category"])
    for activity in base_qs:
        writer.writerow(
            [
                activity.created_at.isoformat(),
                activity.get_action_display(),
                activity.description,
                activity.get_status_display(),
                activity.action,
            ]
        )
    return response


@admin_required
def user_management(request):
    # --- Handle POST actions ---
    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        user = get_object_or_404(User, id=user_id)

        if action == "ban":
            user.is_active = False
            user.save()
            return JsonResponse(
                {"success": True, "message": f"User {user.username} has been banned."}
            )
        elif action == "unban":
            user.is_active = True
            user.save()
            return JsonResponse(
                {"success": True, "message": f"User {user.username} has been unbanned."}
            )
        elif action == "delete":
            user.delete()
            return JsonResponse(
                {"success": True, "message": "User deleted permanently."}
            )

    # --- GET logic ---
    users_qs = User.objects.exclude(is_superuser=True).order_by("-date_joined")

    search_query = request.GET.get("q", "").strip()
    plan_filter = request.GET.get("plan", "all")
    status_filter = request.GET.get("status", "all")

    if search_query:
        users_qs = users_qs.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    if plan_filter != "all":
        if plan_filter == "premium":
            users_qs = users_qs.filter(subscription__plan__slug="premium")
        elif plan_filter == "free":
            users_qs = users_qs.filter(subscription__plan__slug="free")

    if status_filter != "all":
        if status_filter == "active":
            users_qs = users_qs.filter(is_active=True)
        elif status_filter == "deactivated":
            users_qs = users_qs.filter(is_active=False)

    users_qs = users_qs.annotate(total_books=Count("books", distinct=True))

    paginator = Paginator(users_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # --- Build JSON data for modals ---
    users_json = []
    for user in page_obj:
        # Get subscription plan
        sub = getattr(user, "subscription", None)
        plan_slug = sub.plan.slug if sub and sub.plan else "free"

        # Get progress data (chunks for each scheduled book)
        books_progress = []
        for book in user.books.filter(is_scheduled=True).order_by("-created_at")[:5]:
            chunks = book.chunks.order_by("chunk_number")
            total_chunks = chunks.count()
            read_chunks = chunks.filter(is_read=True).count()
            delivered_chunks = chunks.filter(delivered=True).count()
            books_progress.append(
                {
                    "book_id": book.id,
                    "title": book.title,
                    "total_chunks": total_chunks,
                    "read_chunks": read_chunks,
                    "delivered_chunks": delivered_chunks,
                    "status": book.status,
                }
            )

        users_json.append(
            {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name(),
                "email": user.email,
                "is_active": user.is_active,
                "plan": plan_slug,
                "total_books": user.total_books,
                "date_joined": user.date_joined.strftime("%Y-%m-%d"),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "progress": books_progress,
            }
        )

    # Metrics
    total_users = User.objects.exclude(is_superuser=True).count()
    active_users = (
        User.objects.filter(is_active=True).exclude(is_superuser=True).count()
    )
    premium_users = (
        User.objects.filter(subscription__plan__slug="premium")
        .exclude(is_superuser=True)
        .count()
    )
    suspended_users = (
        User.objects.filter(is_active=False).exclude(is_superuser=True).count()
    )

    context = {
        "users": page_obj,
        "page_obj": page_obj,
        "users_json": json.dumps(users_json),
        "total_users": total_users,
        "active_users": active_users,
        "premium_users": premium_users,
        "suspended_users": suspended_users,
        "search_query": search_query,
        "plan_filter": plan_filter,
        "status_filter": status_filter,
    }

    return render(request, "digital/dashboard/user-management.html", context)


@admin_required
def subscript_management(request):
    from django.db.models import Count, Q
    from django.utils import timezone
    from datetime import timedelta

    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)

    # ---- KPIs ----
    active_subs = Subscription.objects.filter(active=True, status="active").count()
    premium_subs = Subscription.objects.filter(
        plan__slug="premium", active=True, status="active"
    ).count()
    free_users = (
        User.objects.exclude(is_superuser=True)
        .filter(Q(subscription__isnull=True) | Q(subscription__plan__slug="free"))
        .count()
    )
    cancelled_30d = Subscription.objects.filter(
        status="cancelled", updated_at__date__gte=thirty_days_ago
    ).count()

    # ---- Subscription Health ----
    health = {
        "active": Subscription.objects.filter(status="active", active=True).count(),
        "trial": Subscription.objects.filter(status="trialing").count(),
        "past_due": Subscription.objects.filter(status="past_due").count(),
        "cancelled": Subscription.objects.filter(status="cancelled").count(),
        "failed": Subscription.objects.filter(status="expired").count(),
    }

    # ---- Plan Distribution ----
    total_subs = Subscription.objects.count() or 1
    free_count = Subscription.objects.filter(plan__slug="free").count()
    premium_count = Subscription.objects.filter(plan__slug="premium").count()
    plan_distribution = {
        "free": free_count,
        "free_pct": int((free_count / total_subs) * 100) if total_subs else 0,
        "premium": premium_count,
        "premium_pct": int((premium_count / total_subs) * 100) if total_subs else 0,
    }

    # ---- Table (paginated) ----
    subs_qs = Subscription.objects.select_related("user", "plan").order_by(
        "-updated_at"
    )

    # Filters
    search = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "all")
    plan_filter = request.GET.get("plan", "all")

    if search:
        subs_qs = subs_qs.filter(
            Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
        )
    if status_filter != "all":
        subs_qs = subs_qs.filter(status=status_filter)
    if plan_filter != "all":
        subs_qs = subs_qs.filter(plan__slug=plan_filter)

    paginator = Paginator(subs_qs, 20)
    page_number = request.GET.get("sub_page")
    page_obj = paginator.get_page(page_number)

    context = {
        "active_subs": active_subs,
        "premium_subs": premium_subs,
        "free_users": free_users,
        "cancelled_30d": cancelled_30d,
        "health": health,
        "plan_distribution": plan_distribution,
        "subscriptions": page_obj,
        "page_obj": page_obj,
        "search": search,
        "status_filter": status_filter,
        "plan_filter": plan_filter,
    }
    return render(request, "digital/subscription-management.html", context)


@admin_required
def revenue(request):
    today = timezone.now().date()

    # ---- Date range filter ----
    range_filter = request.GET.get("range", "30d")
    if range_filter == "today":
        start_date = today
    elif range_filter == "7d":
        start_date = today - timedelta(days=7)
    elif range_filter == "30d":
        start_date = today - timedelta(days=30)
    elif range_filter == "90d":
        start_date = today - timedelta(days=90)
    elif range_filter == "12m":
        start_date = today - timedelta(days=365)
    elif range_filter == "ytd":
        start_date = today.replace(month=1, day=1)
    else:
        start_date = None

    successful = Payment.objects.filter(status="success")
    if start_date:
        successful = successful.filter(transaction_date__date__gte=start_date)

    # ---- KPIs ----
    total_revenue = successful.aggregate(total=Sum("amount"))["total"] or 0

    # MRR: sum of monthly_price of all active premium subscriptions
    mrr = (
        SubscriptionPlan.objects.filter(slug="premium").aggregate(
            total=Sum("monthly_price")
        )["total"]
        or 0
    )
    mrr = (
        Subscription.objects.filter(
            plan__slug="premium", active=True, status="active"
        ).aggregate(total=Sum("plan__monthly_price"))["total"]
        or 0
    )

    arr = mrr * 12

    # Revenue growth (compare current period vs previous period of same length)
    if start_date:
        period_days = (today - start_date).days or 1
        prev_start = start_date - timedelta(days=period_days)
        prev_revenue = (
            Payment.objects.filter(
                status="success",
                transaction_date__date__gte=prev_start,
                transaction_date__date__lt=start_date,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
    else:
        prev_revenue = 0

    if prev_revenue > 0:
        revenue_growth = ((total_revenue - prev_revenue) / prev_revenue) * 100
    elif total_revenue > 0:
        revenue_growth = 100
    else:
        revenue_growth = 0

    # ---- Chart data (last 14 days by default, or full range) ----
    chart_start = start_date or (today - timedelta(days=29))
    labels, values = [], []
    days_to_show = (today - chart_start).days + 1
    days_to_show = min(max(days_to_show, 1), 30)
    for i in range(days_to_show - 1, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%b %d"))
        total = (
            Payment.objects.filter(
                status="success", transaction_date__date=day
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        values.append(float(total))

    revenue_chart_data = {"labels": labels, "values": values} if any(values) else None

    # ---- Revenue by plan ----
    plan_revenue_data = []
    plans = SubscriptionPlan.objects.all()
    grand_total = (
        sum(
            float(
                Payment.objects.filter(
                    status="success",
                    subscription__plan=p,
                    **(
                        {"transaction_date__date__gte": start_date}
                        if start_date
                        else {}
                    ),
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )
            for p in plans
        )
        or 1
    )

    for p in plans:
        subs = Subscription.objects.filter(plan=p, active=True, status="active")
        subs_count = subs.count()
        plan_revenue = (
            Payment.objects.filter(
                status="success",
                subscription__plan=p,
                **({"transaction_date__date__gte": start_date} if start_date else {}),
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        plan_mrr = subs.aggregate(total=Sum("plan__monthly_price"))["total"] or 0
        plan_revenue_data.append(
            {
                "name": p.name,
                "subscribers": subs_count,
                "revenue": plan_revenue,
                "mrr": plan_mrr,
                "percentage": (
                    (float(plan_revenue) / grand_total * 100) if grand_total else 0
                ),
            }
        )

    # ---- Top customers ----
    top_customers_qs = (
        Payment.objects.filter(status="success")
        .values(
            "user__id",
            "user__username",
            "user__email",
            "user__first_name",
            "user__last_name",
        )
        .annotate(
            total_revenue=Sum("amount"),
            payment_count=Count("id"),
            last_payment=Count("id"),  # placeholder
        )
        .order_by("-total_revenue")[:10]
    )

    top_customers = []
    for c in top_customers_qs:
        user_id = c["user__id"]
        last_tx = (
            Payment.objects.filter(user__id=user_id, status="success")
            .order_by("-transaction_date")
            .first()
        )
        # Determine plan
        try:
            sub = Subscription.objects.get(user__id=user_id)
            plan_name = sub.plan.name if sub.plan else "Free"
        except Subscription.DoesNotExist:
            plan_name = "Free"

        top_customers.append(
            {
                "name": f"{c['user__first_name']} {c['user__last_name']}".strip()
                or c["user__username"],
                "email": c["user__email"],
                "plan": plan_name,
                "revenue": c["total_revenue"] or 0,
                "payments": c["payment_count"],
                "last_payment": (
                    last_tx.transaction_date.strftime("%b %d, %Y") if last_tx else "—"
                ),
                "status": "Active",
                "status_class": "success",
            }
        )

    # ---- Recent transactions ----
    recent_qs = (
        Payment.objects.filter(status="success")
        .select_related("user", "subscription__plan")
        .order_by("-transaction_date")[:10]
    )
    transactions = []
    for tx in recent_qs:
        transactions.append(
            {
                "id": tx.reference[:12],
                "customer": tx.user.get_full_name() or tx.user.username,
                "amount": tx.amount,
                "plan": (
                    tx.subscription.plan.name
                    if tx.subscription and tx.subscription.plan
                    else "—"
                ),
                "date": tx.transaction_date.strftime("%b %d, %Y"),
                "payment_method": (
                    tx.metadata.get("payment_method", "Card") if tx.metadata else "Card"
                ),
                "status": tx.get_status_display(),
                "status_class": "success",
            }
        )

    # ---- Revenue events (timeline) ----
    revenue_events = []
    for tx in recent_qs[:5]:
        revenue_events.append(
            {
                "icon": "💰",
                "title": f"Payment received from {tx.user.get_full_name() or tx.user.username}",
                "time": tx.transaction_date.strftime("%b %d, %H:%M"),
                "amount": f"${tx.amount:.2f}",
            }
        )

    context = {
        "range_filter": range_filter,
        "total_revenue": total_revenue,
        "mrr": mrr,
        "arr": arr,
        "revenue_growth": revenue_growth,
        "revenue_chart_data": (
            json.dumps(revenue_chart_data) if revenue_chart_data else None
        ),
        "plan_revenue_data": (
            plan_revenue_data
            if any(p["revenue"] > 0 for p in plan_revenue_data)
            else None
        ),
        "top_customers": top_customers or None,
        "transactions": transactions or None,
        "revenue_events": revenue_events or None,
    }
    return render(request, "digital/revenue.html", context)


@admin_required
def AI_usage (request):
    return render(request, "digital/ai-usage.html")

@admin_required
def book_analytic (request):
    return render (request, "digital/book-analytics.html")


@admin_required
def knowledge_card(request):
    # ... existing analytics data ...
    cards = ChapterSummary.objects.filter(card_image__isnull=False).order_by(
        "-card_generated_at"
    )
    paginator = Paginator(cards, 5)
    page = request.GET.get("page")
    recent_cards = paginator.get_page(page)
    context = {
        # ... other context ...
        "recent_cards": recent_cards,
    }
    return render(request, "digital/knowledge-card.html", context)


@admin_required
def payments(request):
    today = timezone.now().date()

    # ---- Date range filter ----
    range_filter = request.GET.get("range", "30d")
    if range_filter == "today":
        start_date = today
    elif range_filter == "7d":
        start_date = today - timedelta(days=7)
    elif range_filter == "30d":
        start_date = today - timedelta(days=30)
    elif range_filter == "90d":
        start_date = today - timedelta(days=90)
    elif range_filter == "12m":
        start_date = today - timedelta(days=365)
    else:
        start_date = None  # all time

    payments_qs = Payment.objects.select_related("user", "subscription").order_by(
        "-transaction_date"
    )
    if start_date:
        payments_qs = payments_qs.filter(transaction_date__date__gte=start_date)

    # ---- KPIs ----
    total_transactions = payments_qs.count()
    successful_payments = payments_qs.filter(status="success").count()
    payment_volume = (
        payments_qs.filter(status="success").aggregate(total=Sum("amount"))["total"]
        or 0
    )
    avg_tx_value = (payment_volume / successful_payments) if successful_payments else 0

    # ---- Payment Intent Tracker (who clicked pay, and outcome) ----
    payment_intents = []
    for p in payments_qs:
        # Get phone from preferences or profile
        phone = ""
        try:
            if hasattr(p.user, "preferences") and p.user.preferences.phone_number:
                phone = p.user.preferences.phone_number
        except Exception:
            pass
        if not phone:
            try:
                if hasattr(p.user, "profile") and p.user.profile.phone_number:
                    phone = p.user.profile.phone_number
            except Exception:
                pass

        payment_intents.append(
            {
                "name": p.user.get_full_name() or p.user.username,
                "email": p.user.email,
                "phone": phone or "—",
                "status": p.status,  # pending / success / failed
                "amount": p.amount,
                "reference": p.reference,
                "date": p.transaction_date,
            }
        )

    # ---- Recent transactions ----
    recent_transactions = payments_qs[:20]

    # ---- Failed payments ----
    failed_payments = payments_qs.filter(status="failed")[:10]

    # ---- Chart data (last 14 days) ----
    chart_data = None
    if total_transactions > 0:
        labels, success_counts, failed_counts = [], [], []
        for i in range(13, -1, -1):
            day = today - timedelta(days=i)
            labels.append(day.strftime("%b %d"))
            success_counts.append(
                Payment.objects.filter(
                    status="success", transaction_date__date=day
                ).count()
            )
            failed_counts.append(
                Payment.objects.filter(
                    status="failed", transaction_date__date=day
                ).count()
            )
        chart_data = {
            "labels": labels,
            "successful": success_counts,
            "failed": failed_counts,
        }

    # ---- Payment intent click stats (for the small header) ----
    total_clicks = Payment.objects.count()
    pending_clicks = Payment.objects.filter(status="pending").count()

    context = {
        "range_filter": range_filter,
        "total_transactions": total_transactions,
        "successful_payments": successful_payments,
        "payment_volume": payment_volume,
        "avg_tx_value": avg_tx_value,
        "payment_intents": payment_intents,
        "recent_transactions": recent_transactions,
        "failed_payments": failed_payments,
        "chart_data": json.dumps(chart_data) if chart_data else None,
        "total_clicks": total_clicks,
        "pending_clicks": pending_clicks,
    }
    return render(request, "digital/payments.html", context)


def product(request):
    return render(
        request,
        "digital/product.html",
        {
            "is_public_page": True,
        },
    )


@admin_required
def system_settings(request):
    return render(request, 'digital/system-settings.html')


@admin_required
def admin_support(request):
    return render(request, 'digital/admin-support.html')


@login_required
def scheduled_books(request):
    user = request.user
    subscription, _ = Subscription.objects.get_or_create(user=user)
    is_premium = subscription.is_premium()
    prefs, created = UserPreference.objects.get_or_create(user=user)

    # Scheduled books (is_scheduled = True)
    books = Book.objects.filter(user=user, is_scheduled=True).order_by("-created_at")
    for book in books:
        book.chunks_list = book.chunks.all().order_by("chunk_number")
        book.has_delivered_chunk = book.chunks.filter(delivered=True).exists()

    # Unscheduled books for adding
    unscheduled_books = Book.objects.filter(
        user=user, is_scheduled=False, file__isnull=False
    ).order_by("-created_at")

    scheduled_count = books.count()
    max_allowed = 4 if is_premium else 0

    context = {
        "books": books,
        "unscheduled_books": unscheduled_books,
        "prefs": prefs,
        "is_premium": is_premium,
        "scheduled_count": scheduled_count,
        "max_allowed": max_allowed,
        "can_add": is_premium and scheduled_count < max_allowed,
    }
    return render(request, "digital/dashboard/scheduled_books.html", context)


@login_required
def add_to_schedule(request, book_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    user = request.user
    subscription, _ = Subscription.objects.get_or_create(user=user)
    if not subscription.is_premium():
        return JsonResponse(
            {"error": "Upgrade to premium to schedule books"}, status=403
        )
    book = get_object_or_404(Book, id=book_id, user=user)
    if book.is_scheduled:
        return JsonResponse({"error": "Already scheduled"}, status=400)
    scheduled_count = Book.objects.filter(user=user, is_scheduled=True).count()
    if scheduled_count >= 4:
        return JsonResponse({"error": "Maximum 4 books allowed"}, status=400)
    book.is_scheduled = True
    book.save()

    # ====== ADD THIS LINE ======
    log_activity(user, "upload_book", f"Scheduled book: {book.title}")
    # ===========================

    return JsonResponse({"success": True})


@login_required
def remove_from_schedule(request, book_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    user = request.user
    book = get_object_or_404(Book, id=book_id, user=user)
    if not book.is_scheduled:
        return JsonResponse({"error": "Book is not scheduled"}, status=400)
    # Check if any chunk has been delivered
    if book.chunks.filter(delivered=True).exists():
        return JsonResponse(
            {"error": "Delivery already started – cannot remove"}, status=400
        )
    book.is_scheduled = False
    book.save()

    # ====== ADD THIS LINE ======
    log_activity(user, "upload_book", f"Unscheduled book: {book.title}")
    # ===========================

    return JsonResponse({"success": True})


@login_required
def send_chunk_now(request, chunk_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    chunk = get_object_or_404(Chunk, id=chunk_id, book__user=request.user)
    if chunk.delivered:
        return JsonResponse({"error": "Already sent"}, status=400)

    user = request.user
    subscription, _ = Subscription.objects.get_or_create(user=user)
    if not subscription.is_premium():
        return JsonResponse({"error": "Premium subscription required"}, status=403)

    # Respect user's channel preference
    prefs, _ = UserPreference.objects.get_or_create(user=user)
    channel = prefs.channel  # "email" or "whatsapp"

    try:
        if channel == "whatsapp":
            # Only try WhatsApp if a phone number is stored
            if not prefs.phone_number:
                return JsonResponse(
                    {
                        "error": "No WhatsApp number saved. Please update your preferences."
                    },
                    status=400,
                )
            send_chunk_whatsapp(user, chunk)
        else:
            send_chunk_email(user, chunk)

        chunk.delivered = True
        chunk.save()
        return JsonResponse(
            {
                "success": True,
                "message": f"Chunk sent via {channel}.",
            }
        )
    except Exception as e:
        return JsonResponse({"error": f"Send failed: {str(e)}"}, status=500)


@login_required
def update_preferences(request):
    user = request.user
    prefs, created = UserPreference.objects.get_or_create(user=user)

    if request.method == "POST":
        # Default values
        delivery_time = None
        channel = None
        phone_number = ""

        # Check if JSON or form data
        if request.headers.get("Content-Type") == "application/json":
            import json

            data = json.loads(request.body)
            delivery_time = data.get("delivery_time")
            channel = data.get("channel")
            phone_number = data.get("phone_number", "")
        else:
            delivery_time = request.POST.get("delivery_time")
            channel = request.POST.get("channel")
            phone_number = request.POST.get("phone_number", "")

        if delivery_time:
            prefs.delivery_time = delivery_time
        if channel in ["email", "whatsapp"]:
            prefs.channel = channel
        if channel == "whatsapp" and phone_number:
            prefs.phone_number = phone_number
        prefs.save()

        if request.headers.get("Content-Type") == "application/json":
            return JsonResponse({"success": True})
        else:
            messages.success(request, "Preferences updated!")
            return redirect("setting")

    return render(request, "digital/dashboard/settings.html", {"prefs": prefs})


# Create your views here.

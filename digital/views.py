from django.shortcuts import redirect, render, get_object_or_404
from .models import Admin, Lead, Resource, Download
from django.contrib.auth.models import User
from django.db.models import F
from django.http import FileResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re
from django.db.models import Sum, Count


def download_resource(request, slug):
    print(request.session.items())
    resource = get_object_or_404(Resource, slug=slug)

    # Has the visitor submitted the lead form?
    if not request.session.get("lead_verified"):
        return redirect("leads", slug=slug)

    # Get the lead from the session
    lead_id = request.session.get("lead_id")
    lead = get_object_or_404(Lead, id=lead_id)

    # Record the download
    Download.objects.create(
        lead=lead,
        resource=resource,
    )

    # Increment the download count
    Resource.objects.filter(pk=resource.pk).update(
        most_downloaded=F("most_downloaded") + 1
    )

    return FileResponse(
        resource.file.open("rb"),
        as_attachment=True,
        filename=resource.file.name.split("/")[-1],
    )


def home(request):
    resources = Resource.objects.order_by("-created_at")

    paginator = Paginator(resources, 5)  # Show 8 resources per page

    page_number = request.GET.get("page")
    digital_resources = paginator.get_page(page_number)

    top_downloaded_resources = Resource.objects.order_by("-most_downloaded")[:5]
    
    context = {
        "digital_resources": digital_resources,
        "top_downloaded_resources": top_downloaded_resources,
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


@login_required
def admin(request):
    if request.method == "POST":
        thumbnail = request.FILES.get("thumbnail")
        file = request.FILES.get("file")
        title = request.POST.get("title")
        description = request.POST.get("description")

        Resource.objects.create(
            thumbnail=thumbnail,
            file=file,
            title=title,
            description=description,
        )
        return redirect("admin")

    user_count = Lead.objects.count()
    total_resources = Resource.objects.count()

    most_downloaded_resource = Resource.objects.order_by("-most_downloaded").first()

    total_downloads = (
        Resource.objects.aggregate(total=Sum("most_downloaded"))["total"] or 0
    )

    # -------------------------
    # Resources Pagination
    # -------------------------
    resources = Resource.objects.order_by("-most_downloaded")

    resource_paginator = Paginator(resources, 10)
    resource_page = request.GET.get("page")
    resources = resource_paginator.get_page(resource_page)

    # -------------------------
    # Leads Pagination
    # -------------------------
    leads = Lead.objects.order_by("-created_at")

    lead_paginator = Paginator(leads, 10)
    lead_page = request.GET.get("lead_page")
    leads = lead_paginator.get_page(lead_page)

    context = {
        "total_resources": total_resources,
        "resources": resources,
        "most_downloaded_resource": most_downloaded_resource,
        "total_downloads": total_downloads,
        "user_count": user_count,
        "leads": leads,
    }

    return render(request, "digital/admin.html", context)


def resource_detail(request, slug):
    resource = get_object_or_404(Resource, slug=slug)
    top_downloaded_resources = Resource.objects.order_by("-most_downloaded")[:5]
    context = {
        "resource": resource,
        "top_downloaded_resources": top_downloaded_resources,
    }
    return render(request, "digital/resource_detail.html", context)


def create_account(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]

        User.objects.create_user(username=username, email=email, password=password)

        return redirect("login")

    return render(request, "digital/create-account.html")


def login_view(request):
    if request.method == "POST":

        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect("admin")

        return render(
            request,
            "digital/login.html",
            {"error_message": "Invalid username or password"},
        )

    return render(request, "digital/login.html")


def logout_view(request):
    logout(request)
    return redirect("home")


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
        },
    )


def reset_session(request):
    request.session.flush()
    return redirect("home")



def downloads(request):
    leads = (
        Lead.objects.prefetch_related("downloads__resource")
        .annotate(number_of_resources_downloaded=Count("downloads"))
        .order_by("-created_at")
    )

    paginator = Paginator(leads, 10)  # 10 leads per page

    page_number = request.GET.get("page")
    leads = paginator.get_page(page_number)

    return render(
        request,
        "digital/downloads.html",
        {"leads": leads},
    )


# Create your views here.

# ebook/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_view, name="upload"),
    path("progress/<int:book_id>/", views.progress_view, name="progress"),
    path("status/<int:book_id>/", views.status_view, name="status"),
    path("status/<int:book_id>/data/", views.status_data_view, name="status_data"),
    path(
        "book/<int:book_id>/chunk/<int:chunk_id>/", views.reading_view, name="reading"
    ),
]

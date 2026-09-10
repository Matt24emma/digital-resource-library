# ebook/services/storage_service.py
import os
import uuid
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

class TemporaryStorage:
    @staticmethod
    def save_uploaded_file(uploaded_file) -> str:
        """Save uploaded file to temporary location and return absolute path."""
        ext = os.path.splitext(uploaded_file.name)[1]
        filename = f"temp_{uuid.uuid4().hex}{ext}"
        path = default_storage.save(f"tmp/{filename}", ContentFile(uploaded_file.read()))
        return default_storage.path(path)

    @staticmethod
    def delete_file(file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)
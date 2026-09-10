#!/usr/bin/env bash

pip install -r requirements.txt

python manage.py collectstatic --noinput

python manage.py migrate


# Create superuser if it doesn't exist
python manage.py shell << 'EOF'
from django.contrib.auth.models import User
import os

username = os.environ.get("SUPERUSER_USERNAME")
email = os.environ.get("SUPERUSER_EMAIL")
password = os.environ.get("SUPERUSER_PASSWORD")

if username and password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser {username} created.")
else:
    print("Superuser exists or env vars not set. Skipping.")
EOF
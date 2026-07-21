from django.db import models
from django.utils.text import slugify


class Resource(models.Model):
    thumbnail = models.ImageField(upload_to="thumbnails/", null=True, blank=True)
    file = models.FileField(upload_to="resources/")
    title = models.CharField(max_length=100)
    description = models.TextField()
    slug = models.SlugField(unique=True, blank=True)
    most_downloaded = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Resource.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Admin(models.Model):
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    def __str__(self):
        return self.username

class Lead(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Download(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="downloads")

    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="downloads"
    )

    downloaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead.name} downloaded {self.resource.title}"

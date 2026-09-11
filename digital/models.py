from .storages import CloudinaryMediaStorage, CloudinaryRawStorage
from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.utils import timezone
import secrets
from django.db.models.signals import post_save
from django.dispatch import receiver

class Category(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="categories", null=True, blank=True
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Resource(models.Model):
    thumbnail = models.ImageField(
        upload_to="thumbnails/", storage=CloudinaryMediaStorage(), null=True, blank=True
    )
    file = models.FileField(upload_to="resources/", storage=CloudinaryRawStorage())
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


class Book(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="books")
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_scheduled = models.BooleanField(default=False)
    # Fields for ebook splitting
    file = models.FileField(upload_to="user_books/", null=True, blank=True)
    pages_per_day = models.PositiveIntegerField(null=True, blank=True)
    total_pages = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="pending",
    )
    progress = models.IntegerField(default=0)  # 0–100

    def __str__(self):
        return self.title


class ChapterSummary(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="summaries",
    )
    chapter_title = models.CharField(max_length=200)
    main_idea = models.TextField()
    key_lessons = models.TextField()
    concepts = models.TextField()
    examples = models.TextField()
    actions = models.TextField()
    personal_insight = models.TextField()
    card_image = models.ImageField(
        upload_to="card_images/",
        storage=CloudinaryMediaStorage(),
        blank=True,
    )
    card_generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_locked(self):
        """A summary is locked once a card image exists."""
        return bool(self.card_image)

    def __str__(self):
        return f"{self.main_idea}"


class UserCardGeneration(models.Model):
    """Tracks daily card generation count for free users."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="card_generation"
    )
    date = models.DateField(auto_now=True)
    count = models.PositiveIntegerField(default=0)

    def can_generate(self):
        today = timezone.now().date()
        if self.date != today:
            self.date = today
            self.count = 0
            self.save()
        return self.count < 3  # free limit

    def increment(self):
        self.count += 1
        self.save()


class DownloadUsage(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="download_usage"
    )
    downloads_this_month = models.PositiveIntegerField(default=0)
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.downloads_this_month} downloads"


class SubscriptionPlan(models.Model):
    """Defines the available subscription plans (Free, Premium)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    """Stores the user's current subscription state."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
        ("trialing", "Trialing"),
    ]
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    active = models.BooleanField(default=False)
    start_date = models.DateTimeField(default=timezone.now)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    paystack_customer_code = models.CharField(max_length=120, blank=True)
    paystack_subscription_code = models.CharField(max_length=120, blank=True)
    last_renewal_reminder_sent = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_premium(self):
        return (
            self.active
            and self.plan is not None
            and self.plan.slug == "premium"
            and self.status == "active"
        )

    def __str__(self):
        return f"{self.user.username} - {self.plan.name if self.plan else 'No Plan'}"


class Payment(models.Model):
    """Every transaction (successful or failed) made by a user."""

    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("pending", "Pending"),
        ("refunded", "Refunded"),
        ("partially_refunded", "Partially Refunded"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    reference = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    transaction_date = models.DateTimeField(default=timezone.now)
    failure_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.reference} - {self.status}"


class Invoice(models.Model):
    """A formal billing document linked to a subscription period."""

    STATUS_CHOICES = [
        ("paid", "Paid"),
        ("unpaid", "Unpaid"),
        ("void", "Void"),
        ("refunded", "Refunded"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invoices")
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, related_name="invoices"
    )
    payment = models.OneToOneField(
        Payment, on_delete=models.SET_NULL, null=True, related_name="invoice"
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    issue_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField(null=True, blank=True)
    paid_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unpaid")
    pdf_file = models.FileField(upload_to="invoices/", blank=True, null=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.user.email}"


class PaymentEvent(models.Model):
    """Audit log for every financial event (authorization, capture, failure, refund)."""

    TYPE_CHOICES = [
        ("authorization", "Authorization"),
        ("capture", "Capture"),
        ("failure", "Failure"),
        ("refund_requested", "Refund Requested"),
        ("refund_processed", "Refund Processed"),
        ("subscription_created", "Subscription Created"),
        ("subscription_cancelled", "Subscription Cancelled"),
        ("subscription_updated", "Subscription Updated"),
        ("renewal_success", "Renewal Success"),
        ("renewal_failure", "Renewal Failure"),
        ("invoice_generated", "Invoice Generated"),
    ]
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="payment_events"
    )
    event_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.user.email} - {self.event_type} - {self.timestamp}"


class EmailVerification(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="verification"
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def is_expired(self):
        return (timezone.now() - self.created_at).total_seconds() > 86400

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Verification for {self.user.email}"


class ProcessingStage(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="stages")
    stage_name = models.CharField(max_length=50)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Chunk(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chunks")
    chunk_number = models.PositiveIntegerField()
    content = models.TextField()
    page_start = models.PositiveIntegerField()
    page_end = models.PositiveIntegerField()
    chapter_title = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    word_count = models.PositiveIntegerField(null=True, blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    delivered = models.BooleanField(default=False)

    class Meta:
        ordering = ["chunk_number"]


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ("upload_book", "Uploaded Book"),
        ("create_summary", "Created Summary"),
        ("generate_cards", "Generated Knowledge Cards"),
        ("export_pdf", "Exported PDF"),
        ("download_resource", "Downloaded Resource"),
        ("login", "Logged In"),
        ("upgrade", "Upgraded to Premium"),
        ("update_profile", "Updated Profile"),
        ("payment_failed", "Payment Failed"),
        ("payment_success", "Payment Successful"),  # if you want to log success too
    ]
    STATUS_CHOICES = [
        ("success", "Success"),
        ("pending", "Pending"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success")
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True)
    summary = models.ForeignKey(
        ChapterSummary, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.created_at}"


class UserPreference(models.Model):
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
    ]
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="preferences"
    )
    delivery_time = models.TimeField(default="07:00")
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="email")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.channel} at {self.delivery_time}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(
        upload_to="profiles/", storage=CloudinaryMediaStorage(), blank=True, null=True
    )
    profession = models.CharField(max_length=100, blank=True)
    # Add other profile fields as needed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username


# Auto-create profile for every new user
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()


class LeadVisit(models.Model):
    """Logs every visit from a lead, used for analytics."""

    SOURCE_CHOICES = [
        ("direct", "Direct"),
        ("google", "Google Search"),
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("twitter", "Twitter / X"),
        ("linkedin", "LinkedIn"),
        ("whatsapp", "WhatsApp"),
        ("referral", "Referral"),
        ("other", "Other"),
    ]
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="visits")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="direct")
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    visited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-visited_at"]

    def __str__(self):
        return f"{self.lead.email} - {self.source} at {self.visited_at}"


class PageVisit(models.Model):
    """Tracks every page visit (anonymous), used for visitor analytics."""

    SOURCE_CHOICES = [
        ("direct", "Direct"),
        ("google", "Google Search"),
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("twitter", "Twitter / X"),
        ("linkedin", "LinkedIn"),
        ("whatsapp", "WhatsApp"),
        ("referral", "Referral"),
        ("other", "Other"),
    ]
    session_key = models.CharField(max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    referrer = models.CharField(max_length=500, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="direct")
    path = models.CharField(max_length=255, default="/")
    visited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-visited_at"]
        indexes = [
            models.Index(fields=["session_key", "visited_at"]),
            models.Index(fields=["source", "visited_at"]),
        ]

    def __str__(self):
        return f"{self.session_key[:8]}… - {self.source} at {self.visited_at}"

import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _safe_ext(filename):
    """Keep only image extensions so an uploaded file can never be served as HTML or script."""
    ext = os.path.splitext(filename)[1].lower()
    return ext if ext in ALLOWED_IMAGE_EXTENSIONS else ".jpg"


def destination_image_path(instance, filename):
    return f"destinations/{uuid.uuid4().hex}{_safe_ext(filename)}"


def _lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


class Destination(models.Model):
    class Category(models.TextChoices):
        MOUNTAINS = "mountains", "Mountains"
        BEACHES = "beaches", "Beaches"
        HISTORICAL = "historical", "Historical places"
        ADVENTURE = "adventure", "Adventure"

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    place = models.CharField("Country or region", max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices)
    blurb = models.CharField("Short description", max_length=200)
    description = models.TextField(blank=True)
    travel_tip = models.CharField(max_length=250, blank=True)
    image = models.ImageField(upload_to=destination_image_path, blank=True)
    featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["-featured", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("core:destination_detail", args=[self.slug])


class Problem(models.Model):
    ICON_CHOICES = [
        (key, key) for key in
        ("luggage", "bed", "bus", "compass", "wifi", "cloud", "pulse", "card")
    ]

    title = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=20, choices=ICON_CHOICES, default="compass")
    blurb = models.CharField("Short description", max_length=200)
    overview = models.TextField()
    steps = models.TextField(help_text="One step per line, in order.")
    contacts = models.TextField("Who to contact", help_text="One per line.")
    keep_as_proof = models.TextField(help_text="One per line.")
    prevention = models.TextField("How to avoid it", help_text="One per line.")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:problem_detail", args=[self.slug])

    @property
    def steps_list(self):
        return _lines(self.steps)

    @property
    def contacts_list(self):
        return _lines(self.contacts)

    @property
    def proof_list(self):
        return _lines(self.keep_as_proof)

    @property
    def prevention_list(self):
        return _lines(self.prevention)


# ---------------------------------------------------------------------------
# Accounts and reports
# ---------------------------------------------------------------------------

# Report images live outside MEDIA_ROOT so they are never served by URL guess;
# they are only delivered through the permission-checked report_image view.
private_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def report_image_path(instance, filename):
    return f"reports/{uuid.uuid4().hex}{_safe_ext(filename)}"


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    home_country = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"Profile of {self.user}"


class ProblemReport(models.Model):
    CATEGORY_CHOICES = [
        ("lost-luggage-documents", "Lost luggage or documents"),
        ("hotel-cancellations", "Hotel booking cancellation"),
        ("transport-delays", "Delay or vehicle breakdown"),
        ("getting-lost", "Getting lost"),
        ("connectivity", "Internet or GPS problem"),
        ("weather", "Unexpected weather"),
        ("medical-safety", "Medical or safety concern"),
        ("payments-food-bookings", "Food, payment, or booking issue"),
        ("other", "Something else"),
    ]

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        IN_REVIEW = "in_review", "In review"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    title = models.CharField(max_length=140)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    description = models.TextField(max_length=3000)
    location = models.CharField(max_length=160)
    date_of_problem = models.DateField("Date it happened")
    image = models.ImageField(storage=private_storage, upload_to=report_image_path, blank=True)
    share_with_community = models.BooleanField(
        "Share with the community", default=False,
        help_text="Signed-in members will see your username, title, location, and description, and can reply with advice.",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    staff_note = models.TextField("Update from our team", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:report_detail", args=[self.pk])

    def can_be_viewed_by(self, user):
        return bool(
            user.is_authenticated
            and (user.is_staff or self.user_id == user.id or self.share_with_community)
        )

    def can_be_edited_by(self, user):
        """Owners may edit a report until the team starts reviewing it."""
        return bool(
            user.is_authenticated
            and self.user_id == user.id
            and self.status == self.Status.SUBMITTED
        )

    def can_be_deleted_by(self, user):
        return bool(user.is_authenticated and self.user_id == user.id)


class ReportResponse(models.Model):
    report = models.ForeignKey(ProblemReport, on_delete=models.CASCADE, related_name="responses")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="report_responses")
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply by {self.author} on {self.report_id}"


# ---------------------------------------------------------------------------
# Contact messages, notifications, activity history
# ---------------------------------------------------------------------------

class ContactMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="contact_messages")
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=140)
    message = models.TextField(max_length=3000)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} ({self.email})"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=200)
    url = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: {self.message}"


class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="activity")
    action = models.CharField(max_length=80)
    detail = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.user or 'Deleted user'}: {self.action}"

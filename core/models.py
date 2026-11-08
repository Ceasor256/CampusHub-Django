"""
Shared models: campuses, categories, trust & safety, notifications, settings.

Conventions used across CampusHub
- UUID primary keys for anything that appears in a URL.
- Money is integer UGX (PositiveBigIntegerField). Rates are basis points.
- `is_sample` marks seeded development content; it is badged in the UI and
  excluded from analytics.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Institution(TimeStamped):
    class Type(models.TextChoices):
        UNIVERSITY = "university", "University"
        COLLEGE = "college", "College"
        INSTITUTE = "institute", "Institute"

    name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=12)
    slug = models.SlugField(unique=True)
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.UNIVERSITY)
    city = models.CharField(max_length=60)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Campus(TimeStamped):
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="campuses")
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    area = models.CharField(max_length=120, help_text="e.g. Wandegeya, Kampala")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["institution__name", "name"]
        verbose_name_plural = "campuses"

    def __str__(self):
        return f"{self.institution.short_name} · {self.name}"


class Category(TimeStamped):
    class Module(models.TextChoices):
        MARKETPLACE = "marketplace", "Marketplace"
        GIGS = "gigs", "Gigs"

    module = models.CharField(max_length=12, choices=Module.choices)
    slug = models.SlugField()
    name = models.CharField(max_length=60)
    icon = models.CharField(max_length=40, default="package")
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module", "sort_order", "name"]
        verbose_name_plural = "categories"
        constraints = [models.UniqueConstraint(fields=["module", "slug"], name="category_module_slug_uq")]

    def __str__(self):
        return self.name


class Report(TimeStamped):
    """A user report about content or another user. Reviewed by moderators."""

    class Target(models.TextChoices):
        LISTING = "listing", "Listing"
        GIG = "gig", "Gig"
        DEAL = "deal", "Deal"
        BUSINESS = "business", "Business"
        USER = "user", "User"
        MESSAGE = "message", "Message"

    class Reason(models.TextChoices):
        SCAM = "scam_or_fraud", "Scam or fraud"
        PROHIBITED = "prohibited_item", "Prohibited or illegal item"
        ACADEMIC = "academic_dishonesty", "Academic dishonesty"
        HARASSMENT = "harassment", "Harassment or abuse"
        MISLEADING = "misleading", "Misleading or fake"
        SPAM = "spam", "Spam"
        OTHER = "other", "Something else"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_made")
    target_type = models.CharField(max_length=10, choices=Target.choices)
    target_id = models.UUIDField()
    reason = models.CharField(max_length=24, choices=Reason.choices)
    details = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["status", "created_at"]), models.Index(fields=["target_type", "target_id"])]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "target_type", "target_id"],
                condition=Q(status="open"),
                name="report_once_while_open",
            )
        ]


class Review(TimeStamped):
    """Reviews are only possible after a completed gig or recorded sale."""

    class Context(models.TextChoices):
        TRANSACTION = "transaction", "Transaction"
        GIG = "gig", "Gig"

    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_given")
    reviewee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received")
    context_type = models.CharField(max_length=12, choices=Context.choices)
    context_id = models.UUIDField()
    rating = models.PositiveSmallIntegerField()
    comment = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["reviewer", "context_type", "context_id"], name="review_once"),
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5"),
        ]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=300, blank=True)
    link = models.CharField(max_length=200, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]


class AuditLog(models.Model):
    """Append-only record of privileged and security-relevant actions."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)
    target_type = models.CharField(max_length=30, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class PlatformSetting(models.Model):
    """Key/value platform configuration (e.g. commission rates). Changes are audited."""

    key = models.CharField(max_length=60, primary_key=True)
    value = models.JSONField()
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)


class EmailOutbox(models.Model):
    """Development mail capture (core.mail.OutboxBackend). Shown at /dev/outbox/."""

    to = models.CharField(max_length=300)
    subject = models.CharField(max_length=300)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

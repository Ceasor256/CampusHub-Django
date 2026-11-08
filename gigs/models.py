"""
Student tasks & gigs.

Lifecycle:  open --accept--> assigned --both confirm--> completed
              \\--cancel--> cancelled      \\--dispute--> disputed (moderators)
"""

import uuid

from django.conf import settings
from django.db import models

from core.models import TimeStamped


class Gig(TimeStamped):
    class Mode(models.TextChoices):
        IN_PERSON = "in_person", "In person"
        REMOTE = "remote", "Remote"
        EITHER = "either", "In person or remote"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        DISPUTED = "disputed", "Disputed"
        REMOVED = "removed", "Removed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poster = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gigs_posted")
    campus = models.ForeignKey("core.Campus", on_delete=models.PROTECT, related_name="gigs")
    category = models.ForeignKey("core.Category", on_delete=models.PROTECT, related_name="gigs")
    title = models.CharField(max_length=90)
    description = models.TextField(max_length=3000)
    budget_ugx = models.PositiveBigIntegerField()
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.IN_PERSON)
    location_note = models.CharField(max_length=140, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="gigs_assigned")
    agreed_ugx = models.PositiveBigIntegerField(null=True, blank=True)
    poster_confirmed_at = models.DateTimeField(null=True, blank=True)
    worker_confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True)
    is_sample = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "campus", "-created_at"])]

    def __str__(self):
        return self.title


class GigApplication(TimeStamped):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Not selected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gig_applications")
    message = models.TextField(max_length=1000)
    proposed_ugx = models.PositiveBigIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["gig", "applicant"], name="gig_application_uq")]

"""
Money records.

A Transaction is the commercial agreement (a sale or a completed gig). Its
payment state is tracked separately, and the platform fee is a separate,
traceable figure. Payments/PaymentEvents model provider interactions (Phase 2).
"""

import uuid

from django.conf import settings
from django.db import models


class PaymentStatus(models.TextChoices):
    OFFLINE_UNVERIFIED = "offline_unverified", "Paid offline (unverified)"
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    REFUNDED = "refunded", "Refunded"


class Transaction(models.Model):
    class Module(models.TextChoices):
        MARKETPLACE = "marketplace", "Marketplace"
        GIGS = "gigs", "Gigs"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        DISPUTED = "disputed", "Disputed"
        REFUNDED = "refunded", "Refunded"

    class FeeStatus(models.TextChoices):
        NOT_CHARGED = "not_charged", "Not charged"
        ACCRUED = "accrued", "Accrued (owed)"
        COLLECTED = "collected", "Collected"
        WAIVED = "waived", "Waived"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.CharField(max_length=12, choices=Module.choices)
    reference_type = models.CharField(max_length=12)  # "listing" | "gig"
    reference_id = models.UUIDField()
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="purchases")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")
    amount_ugx = models.PositiveBigIntegerField()
    fee_rate_bps = models.PositiveIntegerField(default=0)
    fee_ugx = models.PositiveBigIntegerField(default=0)
    fee_status = models.CharField(max_length=12, choices=FeeStatus.choices, default=FeeStatus.NOT_CHARGED)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.OFFLINE_UNVERIFIED)
    is_test = models.BooleanField(default=False)
    is_sample = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["reference_type", "reference_id"], name="transaction_reference_uq")]


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(Transaction, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=30)
    provider_ref = models.CharField(max_length=100, null=True, blank=True)
    method = models.CharField(max_length=20)  # mtn_momo | airtel_money | card
    amount_ugx = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    is_test = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "provider_ref"], name="payment_provider_ref_uq")]


class PaymentEvent(models.Model):
    """Raw provider webhook events. The unique key makes processing idempotent."""

    provider = models.CharField(max_length=30)
    event_id = models.CharField(max_length=120)
    payload = models.JSONField()
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="payment_event_uq")]

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStamped


class Business(TimeStamped):
    class Kind(models.TextChoices):
        FOOD = "Restaurant / Café"
        PRINT = "Print shop"
        ELECTRONICS = "Electronics"
        FASHION = "Fashion"
        HOSTEL = "Hostel / Accommodation"
        SALON = "Salon / Barber"
        SUPERMARKET = "Supermarket"
        SERVICES = "Services"
        OTHER = "Other"

    class Verification(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Pending review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="businesses")
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True, max_length=90)
    kind = models.CharField(max_length=30, choices=Kind.choices)
    description = models.TextField(max_length=1500)
    phone = models.CharField(max_length=16)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=160)
    verification = models.CharField(max_length=10, choices=Verification.choices, default=Verification.UNVERIFIED)
    verification_note = models.TextField(blank=True, max_length=1000)
    verified_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    is_sample = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "businesses"

    def __str__(self):
        return self.name

    @property
    def is_verified(self):
        return self.verification == self.Verification.VERIFIED


class Promotion(TimeStamped):
    """Paid placement. Only `active` once a succeeded payment is linked."""

    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment"
        ACTIVE = "active"
        ENDED = "ended"
        CANCELLED = "cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="promotions")
    price_ugx = models.PositiveBigIntegerField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    payment = models.ForeignKey("payments.Payment", null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT)


class LiveDealQuerySet(models.QuerySet):
    def live(self):
        now = timezone.now()
        return self.filter(status=Deal.Status.ACTIVE, starts_at__lte=now, ends_at__gt=now, business__status="active")


class Deal(TimeStamped):
    class Status(models.TextChoices):
        PENDING_REVIEW = "pending_review", "In review"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        REJECTED = "rejected", "Rejected"
        REMOVED = "removed", "Removed"

    class Redemption(models.TextChoices):
        UNIQUE_CODE = "unique_code", "Unique code per student (recommended)"
        SHARED_CODE = "shared_code", "Your own promo code"
        SHOW_IN_STORE = "show_in_store", "Show the deal at the counter"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="deals")
    campus = models.ForeignKey("core.Campus", null=True, blank=True, on_delete=models.SET_NULL, help_text="Empty = all campuses")
    title = models.CharField(max_length=90)
    description = models.TextField(max_length=1500)
    terms = models.TextField(blank=True, max_length=800)
    discount_label = models.CharField(max_length=30)
    original_price_ugx = models.PositiveBigIntegerField(null=True, blank=True)
    deal_price_ugx = models.PositiveBigIntegerField(null=True, blank=True)
    redemption = models.CharField(max_length=14, choices=Redemption.choices, default=Redemption.UNIQUE_CODE)
    shared_code = models.CharField(max_length=24, blank=True)
    max_claims = models.PositiveIntegerField(null=True, blank=True)
    claim_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING_REVIEW)
    promotion = models.ForeignKey(Promotion, null=True, blank=True, on_delete=models.SET_NULL)
    is_sample = models.BooleanField(default=False)

    objects = LiveDealQuerySet.as_manager()

    class Meta:
        ordering = ["ends_at"]
        indexes = [models.Index(fields=["status", "ends_at"])]

    def __str__(self):
        return self.title

    @property
    def is_live(self):
        now = timezone.now()
        return self.status == self.Status.ACTIVE and self.starts_at <= now < self.ends_at and self.business.status == "active"

    @property
    def remaining(self):
        return None if self.max_claims is None else max(0, self.max_claims - self.claim_count)

    @property
    def is_sponsored(self):
        p = self.promotion
        now = timezone.now()
        return bool(p and p.status == Promotion.Status.ACTIVE and p.starts_at <= now < p.ends_at)


class DealClaim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="claims")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deal_claims")
    code = models.CharField(max_length=40, unique=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["deal", "user"], name="deal_claim_once")]

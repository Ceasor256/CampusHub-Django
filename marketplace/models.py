import uuid

from django.conf import settings
from django.db import models

from core.models import TimeStamped


class Listing(TimeStamped):
    class Condition(models.TextChoices):
        NEW = "new", "Brand new"
        LIKE_NEW = "like_new", "Like new"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        FOR_PARTS = "for_parts", "For parts"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        SOLD = "sold", "Sold"
        REMOVED = "removed", "Removed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="listings")
    campus = models.ForeignKey("core.Campus", on_delete=models.PROTECT, related_name="listings")
    category = models.ForeignKey("core.Category", on_delete=models.PROTECT, related_name="listings")
    title = models.CharField(max_length=90)
    description = models.TextField(max_length=3000)
    price_ugx = models.PositiveBigIntegerField()
    is_negotiable = models.BooleanField(default=False)
    condition = models.CharField(max_length=10, choices=Condition.choices)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    meetup_note = models.CharField(max_length=140, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    is_sample = models.BooleanField(default=False)
    sold_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "campus", "-created_at"]), models.Index(fields=["seller", "status"])]

    def __str__(self):
        return self.title

    @property
    def cover(self):
        imgs = list(self.images.all())
        return imgs[0] if imgs else None


def listing_image_path(instance, filename):
    return f"listings/{instance.listing_id}/{uuid.uuid4().hex}.webp"


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=listing_image_path)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class Favourite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favourites")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="favourited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "listing"], name="favourite_uq")]

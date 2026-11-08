from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from core.images import MAX_COUNT
from core.models import Category
from core.settings_store import get_commissions
from core.utils import assert_active, audit, compute_fee, conflict, forbidden, invalid, not_found, notify
from payments.models import Transaction

from .models import Favourite, Listing, ListingImage

PAGE_SIZE = 24


def card_queryset():
    return Listing.objects.select_related("campus__institution", "category").prefetch_related(
        Prefetch("images", queryset=ListingImage.objects.order_by("sort_order", "id"))
    )


def search(*, q="", campus=None, category="", condition="", min_price=None, max_price=None, sort="newest"):
    qs = card_queryset().filter(status=Listing.Status.ACTIVE)
    if campus:
        qs = qs.filter(campus=campus)
    if category:
        qs = qs.filter(category__slug=category, category__module="marketplace")
    if condition in Listing.Condition.values:
        qs = qs.filter(condition=condition)
    if min_price is not None:
        qs = qs.filter(price_ugx__gte=min_price)
    if max_price is not None:
        qs = qs.filter(price_ugx__lte=max_price)
    q = (q or "").strip()[:80]
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    order = {"price_asc": ["price_ugx", "-created_at"], "price_desc": ["-price_ugx", "-created_at"]}.get(sort, ["-created_at"])
    return qs.order_by(*order)


def get_for_viewer(listing_id, viewer):
    listing = card_queryset().select_related("seller").filter(pk=listing_id).first()
    if not listing:
        raise not_found("That listing")
    is_owner = viewer.is_authenticated and viewer.pk == listing.seller_id
    can_mod = viewer.is_authenticated and viewer.can_moderate
    if listing.status == Listing.Status.REMOVED and not can_mod:
        raise not_found("That listing")
    if listing.status == Listing.Status.PAUSED and not (is_owner or can_mod):
        raise not_found("That listing")
    return listing, is_owner


def _category_or_error(category_id, module):
    c = Category.objects.filter(pk=category_id, module=module, is_active=True).first()
    if not c:
        raise invalid("Choose a valid category.")
    return c


@transaction.atomic
def create_listing(user, data, images):
    assert_active(user)
    _category_or_error(data["category"].pk, "marketplace")
    listing = Listing.objects.create(seller=user, **data)
    for i, f in enumerate(images):
        ListingImage.objects.create(listing=listing, image=f, sort_order=i)
    return listing


def _owned(user, listing_id):
    listing = Listing.objects.filter(pk=listing_id).first()
    if not listing or listing.status == Listing.Status.REMOVED:
        raise not_found("That listing")
    if listing.seller_id != user.pk:
        raise forbidden("Only the seller can change this listing.")
    return listing


@transaction.atomic
def update_listing(user, listing_id, data, *, keep_ids, new_images):
    assert_active(user)
    listing = _owned(user, listing_id)
    if listing.status == Listing.Status.SOLD:
        raise conflict("Sold listings can't be edited.")
    _category_or_error(data["category"].pk, "marketplace")
    kept = list(listing.images.filter(pk__in=keep_ids))
    if len(kept) + len(new_images) > MAX_COUNT:
        raise invalid(f"You can add up to {MAX_COUNT} photos.")
    for k, v in data.items():
        setattr(listing, k, v)
    listing.save()
    for img in listing.images.exclude(pk__in=[k.pk for k in kept]):
        img.image.delete(save=False)
        img.delete()
    for i, img in enumerate(kept):
        img.sort_order = i
        img.save(update_fields=["sort_order"])
    for j, f in enumerate(new_images):
        ListingImage.objects.create(listing=listing, image=f, sort_order=len(kept) + j)
    return listing


def set_paused(user, listing_id, paused):
    assert_active(user)
    listing = _owned(user, listing_id)
    if listing.status == Listing.Status.SOLD:
        raise conflict("This listing is already sold.")
    listing.status = Listing.Status.PAUSED if paused else Listing.Status.ACTIVE
    listing.save(update_fields=["status", "updated_at"])


@transaction.atomic
def delete_listing(user, listing_id):
    assert_active(user)
    listing = _owned(user, listing_id)
    if Transaction.objects.filter(reference_type="listing", reference_id=listing.pk).exists():
        # Keep history for sold items; hide instead of erasing.
        listing.status = Listing.Status.REMOVED
        listing.save(update_fields=["status", "updated_at"])
        return
    for img in listing.images.all():
        img.image.delete(save=False)
    listing.delete()


def contacts(user, listing):
    """People who messaged the seller about this listing: candidate buyers."""
    from accounts.models import User

    return User.objects.filter(conversation_memberships__conversation__listing=listing).exclude(pk=user.pk).distinct()


@transaction.atomic
def mark_sold(user, listing_id, *, buyer_id, final_price):
    """
    Records the sale. Payment happened outside CampusHub, so it's
    offline_unverified. A fee is only accrued when commissions are enabled.
    """
    assert_active(user)
    listing = _owned(user, listing_id)
    buyer = None
    if buyer_id:
        buyer = contacts(user, listing).filter(pk=buyer_id).first()
        if not buyer:
            raise invalid("The buyer must be someone who messaged you about this item.")
    # Conditional update: only one request can move it to sold.
    if not Listing.objects.filter(pk=listing.pk).exclude(status=Listing.Status.SOLD).update(status=Listing.Status.SOLD, sold_at=timezone.now()):
        raise conflict("This listing is already marked as sold.")
    c = get_commissions()
    rate = c.rates["marketplace"] if c.enabled else 0
    tx = Transaction.objects.create(
        module="marketplace",
        reference_type="listing",
        reference_id=listing.pk,
        buyer=buyer,
        seller=user,
        amount_ugx=final_price,
        fee_rate_bps=rate,
        fee_ugx=compute_fee(final_price, rate),
        fee_status="accrued" if rate else "not_charged",
        status="completed",
        payment_status="offline_unverified",
        is_sample=listing.is_sample,
        completed_at=timezone.now(),
    )
    if buyer:
        notify(buyer, "listing.sold_to_you", f'You bought "{listing.title}"', "Your purchase is recorded in Me → Purchases.", "/me/?tab=purchases")
    audit(user, "listing.mark_sold", "listing", listing.pk, {"transaction": str(tx.pk)})
    return tx


def toggle_favourite(user, listing_id):
    assert_active(user)
    deleted, _ = Favourite.objects.filter(user=user, listing_id=listing_id).delete()
    if deleted:
        return False
    if not Listing.objects.filter(pk=listing_id, status__in=["active", "sold"]).exists():
        raise not_found("That listing")
    Favourite.objects.get_or_create(user=user, listing_id=listing_id)
    return True


def increment_views(listing):
    from django.db.models import F

    Listing.objects.filter(pk=listing.pk).update(view_count=F("view_count") + 1)


def seller_stats(seller):
    return Listing.objects.filter(seller=seller).aggregate(active=Count("id", filter=Q(status="active")), sold=Count("id", filter=Q(status="sold")))

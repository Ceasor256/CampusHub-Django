"""
Businesses and campus deals.

- Deals from verified businesses go live immediately; others wait for review.
- Claims are unique per user per deal and capped by max_claims atomically.
- Codes are redeemed once, by the business owner, and the redemption is audited.
- "Sponsored" placement requires an active Promotion backed by a payment.
"""

import secrets

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from django.utils.text import slugify

from core.utils import assert_active, audit, conflict, forbidden, invalid, not_found, notify

from .models import Business, Deal, DealClaim

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def _code(prefix="CH"):
    return prefix + "-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


# ------------------------------------------------------------------ businesses
def create_business(user, data):
    assert_active(user)
    if Business.objects.filter(owner=user).count() >= 3:
        raise conflict("You can manage up to 3 business profiles. Contact support for more.")
    base = slugify(data["name"])[:80] or "business"
    slug, i = base, 2
    while Business.objects.filter(slug=slug).exists():
        slug, i = f"{base}-{i}", i + 1
    b = Business.objects.create(owner=user, slug=slug, **data)
    audit(user, "business.create", "business", b.pk)
    return b


def owned_business(user, business_id):
    b = Business.objects.filter(pk=business_id).first()
    if not b:
        raise not_found("That business")
    if b.owner_id != user.pk:
        raise forbidden("Only the business owner can do that.")
    return b


def update_business(user, business_id, data):
    assert_active(user)
    b = owned_business(user, business_id)
    # Renaming a verified business sends it back for review.
    if b.is_verified and b.name != data["name"]:
        b.verification, b.verified_at = Business.Verification.PENDING, None
    for k, v in data.items():
        setattr(b, k, v)
    b.save()
    return b


def request_verification(user, business_id, note):
    assert_active(user)
    b = owned_business(user, business_id)
    if b.verification == Business.Verification.VERIFIED:
        raise conflict("This business is already verified.")
    if b.verification == Business.Verification.PENDING:
        raise conflict("Verification is already in review.")
    if len(note.strip()) < 20:
        raise invalid("Tell us how to verify you (at least 20 characters).")
    b.verification, b.verification_note = Business.Verification.PENDING, note[:1000]
    b.save()


def business_for_viewer(slug, viewer):
    b = Business.objects.filter(slug=slug).first()
    if not b:
        raise not_found("That business")
    if b.status == "suspended" and not (viewer.is_authenticated and (viewer.pk == b.owner_id or viewer.can_moderate)):
        raise not_found("That business")
    return b


# ------------------------------------------------------------------ deals
def live_deals(campus=None, business=None):
    qs = Deal.objects.live().select_related("business", "campus", "promotion")
    if campus:
        qs = qs.filter(Q(campus__isnull=True) | Q(campus=campus))
    if business:
        qs = qs.filter(business=business)
    now = timezone.now()
    sponsored = Q(promotion__status="active", promotion__starts_at__lte=now, promotion__ends_at__gt=now)
    return qs.annotate(sponsored_rank=Count("id", filter=sponsored)).order_by("-sponsored_rank", "ends_at")


def get_deal(deal_id, viewer):
    d = Deal.objects.select_related("business", "campus", "promotion").filter(pk=deal_id).first()
    if not d:
        raise not_found("That deal")
    is_owner = viewer.is_authenticated and d.business.owner_id == viewer.pk
    can_mod = viewer.is_authenticated and viewer.can_moderate
    if d.status != Deal.Status.ACTIVE and not (is_owner or can_mod):
        raise not_found("That deal")
    return d, is_owner


def create_deal(user, business_id, data):
    assert_active(user)
    b = owned_business(user, business_id)
    if b.status != "active":
        raise forbidden("This business is suspended.")
    status = Deal.Status.ACTIVE if b.is_verified else Deal.Status.PENDING_REVIEW
    if data.get("redemption") != Deal.Redemption.SHARED_CODE:
        data["shared_code"] = ""
    d = Deal.objects.create(business=b, status=status, **data)
    audit(user, "deal.create", "deal", d.pk, {"status": status})
    return d


def set_paused_by_owner(user, deal_id, paused):
    assert_active(user)
    d = Deal.objects.filter(pk=deal_id).first()
    if not d:
        raise not_found("That deal")
    owned_business(user, d.business_id)
    if d.status not in (Deal.Status.ACTIVE, Deal.Status.PAUSED):
        raise conflict("Only live deals can be paused or resumed.")
    d.status = Deal.Status.PAUSED if paused else Deal.Status.ACTIVE
    d.save(update_fields=["status", "updated_at"])


@transaction.atomic
def claim(user, deal_id):
    assert_active(user)
    d = Deal.objects.live().select_related("business").filter(pk=deal_id).first()
    if not d:
        raise conflict("This deal isn't available right now.")
    if d.business.owner_id == user.pk:
        raise invalid("You can't claim your own business's deal.")
    if d.campus_id and d.campus_id != user.campus_id:
        raise invalid("This deal is only for students at a specific campus.")
    existing = DealClaim.objects.filter(deal=d, user=user).first()
    if existing:
        return existing
    # Atomic capacity check: only increments while there is room left.
    room = Q(max_claims__isnull=True) | Q(claim_count__lt=F("max_claims"))
    if not Deal.objects.filter(room, pk=d.pk).update(claim_count=F("claim_count") + 1):
        raise conflict("All claims for this deal have been taken.")
    prefix = d.shared_code if d.redemption == Deal.Redemption.SHARED_CODE and d.shared_code else "CH"
    for _ in range(5):
        try:
            with transaction.atomic():
                return DealClaim.objects.create(deal=d, user=user, code=_code(prefix))
        except IntegrityError:
            if DealClaim.objects.filter(deal=d, user=user).exists():
                raise conflict("You've already claimed this deal.")
    raise conflict("Couldn't generate a code. Please try again.")


@transaction.atomic
def redeem(user, business_id, raw_code):
    """Business staff redeem a student's code at the counter. Single use."""
    assert_active(user)
    owned_business(user, business_id)
    code = (raw_code or "").strip().upper()
    c = DealClaim.objects.select_related("deal", "user").filter(code=code, deal__business_id=business_id).first()
    if not c:
        raise not_found("That code")
    if c.redeemed_at:
        when = timezone.localtime(c.redeemed_at).strftime("%d %b %Y, %H:%M")
        raise conflict(f"Already redeemed on {when}.")
    if not DealClaim.objects.filter(pk=c.pk, redeemed_at__isnull=True).update(redeemed_at=timezone.now()):
        raise conflict("Already redeemed.")
    audit(user, "deal.redeem", "deal_claim", c.pk)
    notify(c.user, "deal.redeemed", f"Deal redeemed: {c.deal.title}", link=f"/deals/{c.deal_id}/")
    return c


def increment_views(deal):
    Deal.objects.filter(pk=deal.pk).update(view_count=F("view_count") + 1)


def dashboard(user, business_id):
    b = owned_business(user, business_id)
    deals = (
        b.deals.exclude(status=Deal.Status.REMOVED)
        .annotate(redeemed=Count("claims", filter=Q(claims__redeemed_at__isnull=False)))
        .order_by("-created_at")
    )
    return b, list(deals)

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from core.models import Category, Report, Review
from core.settings_store import get_commissions
from core.utils import assert_active, audit, compute_fee, conflict, forbidden, invalid, not_found, notify
from payments.models import Transaction

from .models import Gig, GigApplication

ACTIVE_APPS = ~Q(applications__status=GigApplication.Status.WITHDRAWN)


def card_queryset():
    return Gig.objects.select_related("campus__institution", "category", "poster").annotate(
        applicant_count=Count("applications", filter=ACTIVE_APPS)
    )


def search(*, q="", campus=None, category="", mode=""):
    qs = card_queryset().filter(status=Gig.Status.OPEN)
    if campus:
        qs = qs.filter(campus=campus)
    if category:
        qs = qs.filter(category__slug=category, category__module="gigs")
    if mode == "remote":
        qs = qs.filter(mode__in=["remote", "either"])
    elif mode == "in_person":
        qs = qs.filter(mode__in=["in_person", "either"])
    q = (q or "").strip()[:80]
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    return qs.order_by("-created_at")


def get_gig(gig_id, viewer=None):
    gig = card_queryset().select_related("assignee").filter(pk=gig_id).first()
    if not gig or (gig.status == Gig.Status.REMOVED and not (viewer and viewer.is_authenticated and viewer.can_moderate)):
        raise not_found("That gig")
    return gig


def _load(gig_id):
    gig = Gig.objects.filter(pk=gig_id).first()
    if not gig or gig.status == Gig.Status.REMOVED:
        raise not_found("That gig")
    return gig


def create_gig(user, data):
    assert_active(user)
    if not Category.objects.filter(pk=data["category"].pk, module="gigs", is_active=True).exists():
        raise invalid("Choose a valid category.")
    return Gig.objects.create(poster=user, **data)


@transaction.atomic
def apply(user, gig_id, *, message, proposed_ugx):
    assert_active(user)
    gig = _load(gig_id)
    if gig.poster_id == user.pk:
        raise invalid("You can't apply to your own gig.")
    if gig.status != Gig.Status.OPEN:
        raise conflict("This gig is no longer accepting applications.")
    existing = GigApplication.objects.filter(gig=gig, applicant=user).first()
    if existing and existing.status != GigApplication.Status.WITHDRAWN:
        raise conflict("You've already applied to this gig.")
    if existing:
        existing.message, existing.proposed_ugx, existing.status = message, proposed_ugx, GigApplication.Status.PENDING
        existing.save()
    else:
        GigApplication.objects.create(gig=gig, applicant=user, message=message, proposed_ugx=proposed_ugx)
    notify(gig.poster, "gig.application", f'New application for "{gig.title}"', f"{user.full_name} applied.", f"/gigs/{gig.pk}/")


def withdraw(user, gig_id):
    assert_active(user)
    n = GigApplication.objects.filter(gig_id=gig_id, applicant=user, status=GigApplication.Status.PENDING).update(
        status=GigApplication.Status.WITHDRAWN, updated_at=timezone.now()
    )
    if not n:
        raise conflict("There's no pending application to withdraw.")


@transaction.atomic
def accept(user, application_id):
    assert_active(user)
    app = GigApplication.objects.select_related("gig", "applicant").filter(pk=application_id).first()
    if not app:
        raise not_found("That application")
    gig = app.gig
    if gig.poster_id != user.pk:
        raise forbidden("Only the gig poster can choose a provider.")
    if app.status != GigApplication.Status.PENDING:
        raise conflict("This application is no longer pending.")
    # Conditional update guards against two accepts racing each other.
    moved = Gig.objects.filter(pk=gig.pk, status=Gig.Status.OPEN).update(
        status=Gig.Status.ASSIGNED, assignee=app.applicant, agreed_ugx=app.proposed_ugx, updated_at=timezone.now()
    )
    if not moved:
        raise conflict("This gig has already been assigned.")
    app.status = GigApplication.Status.ACCEPTED
    app.save(update_fields=["status", "updated_at"])
    others = list(GigApplication.objects.filter(gig=gig, status=GigApplication.Status.PENDING).select_related("applicant"))
    GigApplication.objects.filter(pk__in=[o.pk for o in others]).update(status=GigApplication.Status.REJECTED)
    notify(app.applicant, "gig.accepted", f'You got the gig: "{gig.title}"', "Message the poster to agree on the details.", f"/gigs/{gig.pk}/")
    for o in others:
        notify(o.applicant, "gig.filled", f'"{gig.title}" was filled', link="/gigs/")


@transaction.atomic
def confirm_completion(user, gig_id):
    """Either party confirms; when both have, the gig completes and a transaction is recorded."""
    assert_active(user)
    gig = Gig.objects.select_for_update().filter(pk=gig_id).first()
    if not gig or gig.status == Gig.Status.REMOVED:
        raise not_found("That gig")
    if gig.status != Gig.Status.ASSIGNED:
        raise conflict("Only assigned gigs can be completed.")
    is_poster, is_worker = gig.poster_id == user.pk, gig.assignee_id == user.pk
    if not (is_poster or is_worker):
        raise forbidden()
    now = timezone.now()
    if is_poster:
        gig.poster_confirmed_at = gig.poster_confirmed_at or now
    else:
        gig.worker_confirmed_at = gig.worker_confirmed_at or now
    if gig.poster_confirmed_at and gig.worker_confirmed_at:
        gig.status, gig.completed_at = Gig.Status.COMPLETED, now
        gig.save()
        c = get_commissions()
        rate = c.rates["gigs"] if c.enabled else 0
        amount = gig.agreed_ugx or gig.budget_ugx
        Transaction.objects.get_or_create(
            reference_type="gig",
            reference_id=gig.pk,
            defaults=dict(
                module="gigs", buyer_id=gig.poster_id, seller_id=gig.assignee_id, amount_ugx=amount, fee_rate_bps=rate,
                fee_ugx=compute_fee(amount, rate), fee_status="accrued" if rate else "not_charged", status="completed",
                payment_status="offline_unverified", is_sample=gig.is_sample, completed_at=now,
            ),
        )
        for uid in (gig.poster, gig.assignee):
            notify(uid, "gig.completed", f'"{gig.title}" is complete', "Leave a review to build trust on CampusHub.", f"/gigs/{gig.pk}/")
        return "completed"
    gig.save()
    other = gig.assignee if is_poster else gig.poster
    notify(other, "gig.confirm_requested", f'{user.full_name} marked "{gig.title}" as done', "Confirm when you're satisfied.", f"/gigs/{gig.pk}/")
    return "waiting"


@transaction.atomic
def cancel(user, gig_id, reason):
    assert_active(user)
    gig = _load(gig_id)
    if gig.poster_id != user.pk:
        raise forbidden("Only the poster can cancel this gig.")
    if gig.status not in (Gig.Status.OPEN, Gig.Status.ASSIGNED):
        raise conflict("This gig can no longer be cancelled.")
    if gig.status == Gig.Status.ASSIGNED and gig.worker_confirmed_at:
        raise conflict("The provider already marked this as done. Confirm it, or open a dispute if there's a problem.")
    gig.status, gig.cancel_reason = Gig.Status.CANCELLED, (reason or "")[:300]
    gig.save()
    pending = list(GigApplication.objects.filter(gig=gig, status=GigApplication.Status.PENDING).select_related("applicant"))
    GigApplication.objects.filter(pk__in=[p.pk for p in pending]).update(status=GigApplication.Status.REJECTED)
    targets = {p.applicant for p in pending} | ({gig.assignee} if gig.assignee else set())
    for u in targets:
        notify(u, "gig.cancelled", f'"{gig.title}" was cancelled', reason, f"/gigs/{gig.pk}/")


@transaction.atomic
def dispute(user, gig_id, details):
    assert_active(user)
    gig = _load(gig_id)
    if user.pk not in (gig.poster_id, gig.assignee_id):
        raise forbidden()
    if gig.status != Gig.Status.ASSIGNED:
        raise conflict("Only gigs in progress can be disputed.")
    if len((details or "").strip()) < 10:
        raise invalid("Please describe the problem (at least 10 characters).")
    gig.status = Gig.Status.DISPUTED
    gig.save(update_fields=["status", "updated_at"])
    Report.objects.get_or_create(
        reporter=user, target_type="gig", target_id=gig.pk, status="open",
        defaults={"reason": "other", "details": f"DISPUTE: {details[:1000]}"},
    )
    other = gig.assignee if user.pk == gig.poster_id else gig.poster
    notify(other, "gig.disputed", f'A dispute was opened on "{gig.title}"', "A CampusHub moderator will review it.", f"/gigs/{gig.pk}/")
    audit(user, "gig.dispute", "gig", gig.pk)


def review(user, gig_id, *, rating, comment):
    assert_active(user)
    gig = _load(gig_id)
    if gig.status != Gig.Status.COMPLETED:
        raise conflict("You can review once the gig is completed.")
    reviewee = gig.assignee if user.pk == gig.poster_id else gig.poster if user.pk == gig.assignee_id else None
    if not reviewee:
        raise forbidden()
    try:
        with transaction.atomic():
            Review.objects.create(reviewer=user, reviewee=reviewee, context_type="gig", context_id=gig.pk, rating=rating, comment=comment or "")
    except IntegrityError:
        raise conflict("You've already reviewed this gig.")
    notify(reviewee, "review.received", f"{user.full_name} left you a {rating}★ review", link=f"/u/{reviewee.pk}/")

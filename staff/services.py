"""
Reports, moderation and administration. Every privileged action is
permission-checked here and written to the audit log.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import StaffRole
from core.models import Campus, Category, Institution, Report
from core.utils import assert_active, assert_admin, assert_moderator, assert_staff, audit, conflict, invalid, not_found, notify
from deals.models import Business, Deal, DealClaim
from gigs.models import Gig
from marketplace.models import Listing
from messaging.models import Message
from payments.models import Transaction

User = get_user_model()

TARGETS = {"listing": Listing, "gig": Gig, "deal": Deal, "business": Business, "user": User, "message": Message}


# ------------------------------------------------------------------ reports
def create_report(user, *, target_type, target_id, reason, details):
    assert_active(user)
    model = TARGETS.get(target_type)
    if not model or not model.objects.filter(pk=target_id).exists():
        raise not_found("The reported item")
    if target_type == "user" and str(target_id) == str(user.pk):
        raise invalid("You can't report yourself.")
    try:
        with transaction.atomic():
            return Report.objects.create(reporter=user, target_type=target_type, target_id=target_id, reason=reason, details=details or "")
    except IntegrityError:
        raise conflict("You've already reported this. Our team is reviewing it.")


def describe_target(target_type, target_id):
    """Human-readable label, link, owner and status for a report target."""
    model = TARGETS.get(target_type)
    obj = model.objects.filter(pk=target_id).first() if model else None
    if obj is None:
        return {"label": f"(deleted {target_type})", "href": None, "owner": None, "status": None}
    match target_type:
        case "listing":
            return {"label": obj.title, "href": f"/marketplace/{obj.pk}/", "owner": obj.seller, "status": obj.status}
        case "gig":
            return {"label": obj.title, "href": f"/gigs/{obj.pk}/", "owner": obj.poster, "status": obj.status}
        case "deal":
            return {"label": obj.title, "href": f"/deals/{obj.pk}/", "owner": obj.business.owner, "status": obj.status}
        case "business":
            return {"label": obj.name, "href": f"/b/{obj.slug}/", "owner": obj.owner, "status": obj.status}
        case "user":
            return {"label": obj.full_name, "href": f"/u/{obj.pk}/", "owner": obj, "status": obj.status}
        case "message":
            return {"label": f"“{obj.body[:140]}”", "href": None, "owner": obj.sender, "status": None}


def list_reports(user, status="open"):
    assert_staff(user)
    rows = Report.objects.filter(status=status).select_related("reporter", "resolved_by")
    rows = rows.order_by("created_at" if status == "open" else "-resolved_at")[:100]
    return [{"r": r, "target": describe_target(r.target_type, r.target_id)} for r in rows]


def _remove_content(target_type, target_id):
    if target_type == "listing":
        Listing.objects.filter(pk=target_id).update(status="removed")
    elif target_type == "gig":
        Gig.objects.filter(pk=target_id).update(status="removed")
    elif target_type == "deal":
        Deal.objects.filter(pk=target_id).update(status="removed")
    elif target_type == "business":
        Business.objects.filter(pk=target_id).update(status="suspended")
    elif target_type == "message":
        Message.objects.filter(pk=target_id).update(body="[Message removed by CampusHub moderators]")


def _suspend(actor, target, reason):
    if target.pk == actor.pk:
        raise invalid("You can't suspend yourself.")
    if target.is_platform_admin and not actor.is_platform_admin:
        raise invalid("Only admins can suspend an admin.")
    target.status, target.suspended_reason = User.Status.SUSPENDED, reason[:500]
    target.save(update_fields=["status", "suspended_reason"])
    _end_sessions(target)
    audit(actor, "user.suspend", "user", target.pk, {"reason": reason})


def _end_sessions(user):
    """Sign a user out everywhere (DB-backed sessions)."""
    for s in Session.objects.filter(expire_date__gt=timezone.now()):
        if s.get_decoded().get("_auth_user_id") == str(user.pk):
            s.delete()


@transaction.atomic
def resolve_report(actor, report_id, *, outcome, note):
    assert_moderator(actor)
    r = Report.objects.filter(pk=report_id).first()
    if not r:
        raise not_found("That report")
    if r.status != "open":
        raise conflict("This report has already been resolved.")
    if outcome not in {"dismiss", "remove", "remove_and_suspend"}:
        raise invalid("Invalid outcome.")
    target = describe_target(r.target_type, r.target_id)
    if outcome != "dismiss":
        _remove_content(r.target_type, r.target_id)
        if outcome == "remove_and_suspend" and target["owner"]:
            _suspend(actor, target["owner"], f"Report {r.pk}: {note}")
    # Resolve every open report on the same target together.
    Report.objects.filter(target_type=r.target_type, target_id=r.target_id, status="open").update(
        status="dismissed" if outcome == "dismiss" else "actioned", resolved_by=actor, resolved_at=timezone.now(), resolution_note=note[:1000]
    )
    audit(actor, f"report.{outcome}", r.target_type, r.target_id, {"report": str(r.pk), "note": note})
    if outcome != "dismiss" and target["owner"] and r.target_type != "user":
        notify(target["owner"], "moderation.removed", f'Your {r.target_type} "{target["label"][:60]}" was removed',
               "It broke CampusHub's community guidelines. Reply to support@campushub.ug to appeal.", "/safety/")


# ------------------------------------------------------------------ users
def list_users(actor, *, q="", status=""):
    assert_staff(actor)
    qs = User.objects.prefetch_related("staff_roles").order_by("-date_joined")
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    if status in User.Status.values:
        qs = qs.filter(status=status)
    return qs


def suspend_user(actor, user_id, reason):
    assert_moderator(actor)
    if len(reason.strip()) < 5:
        raise invalid("Give a reason (at least 5 characters).")
    target = User.objects.filter(pk=user_id).first()
    if not target:
        raise not_found("That user")
    with transaction.atomic():
        _suspend(actor, target, reason)


def restore_user(actor, user_id):
    assert_moderator(actor)
    if not User.objects.filter(pk=user_id, status="suspended").update(status="active", suspended_reason=""):
        raise conflict("This user isn't suspended.")
    audit(actor, "user.restore", "user", user_id)
    notify(User.objects.get(pk=user_id), "account.restored", "Your account has been restored", link="/")


def set_role(actor, user_id, role, grant):
    assert_admin(actor)
    if role not in StaffRole.Role.values:
        raise invalid("Invalid role.")
    if str(user_id) == str(actor.pk) and role == "admin" and not grant:
        raise invalid("You can't remove your own admin role.")
    if grant:
        StaffRole.objects.get_or_create(user_id=user_id, role=role, defaults={"granted_by": actor})
    else:
        StaffRole.objects.filter(user_id=user_id, role=role).delete()
    audit(actor, "role.grant" if grant else "role.revoke", "user", user_id, {"role": role})


def set_student_verified(actor, user_id, verified):
    assert_moderator(actor)
    User.objects.filter(pk=user_id).update(student_verified_at=timezone.now() if verified else None)
    audit(actor, "user.student_verify" if verified else "user.student_unverify", "user", user_id)


# ------------------------------------------------------------------ businesses & deals
def set_business_verification(actor, business_id, decision, note):
    assert_moderator(actor)
    b = Business.objects.filter(pk=business_id).first()
    if not b:
        raise not_found("That business")
    b.verification = decision
    b.verified_at = timezone.now() if decision == "verified" else None
    b.verification_note = note
    b.save()
    audit(actor, f"business.{decision}", "business", b.pk, {"note": note})
    notify(b.owner, "business.verification",
           f"{b.name} is now verified ✓" if decision == "verified" else f"{b.name} verification was not approved", note, f"/business/{b.pk}/")


def set_business_suspended(actor, business_id, suspended):
    assert_moderator(actor)
    Business.objects.filter(pk=business_id).update(status="suspended" if suspended else "active")
    audit(actor, "business.suspend" if suspended else "business.restore", "business", business_id)


def moderate_deal(actor, deal_id, decision):
    assert_moderator(actor)
    if decision not in {"active", "rejected", "removed"}:
        raise invalid("Invalid decision.")
    d = Deal.objects.select_related("business__owner").filter(pk=deal_id).first()
    if not d:
        raise not_found("That deal")
    d.status = decision
    d.save(update_fields=["status", "updated_at"])
    audit(actor, f"deal.{decision}", "deal", d.pk)
    notify(d.business.owner, "deal.moderated",
           f'Your deal "{d.title}" is live' if decision == "active" else f'Your deal "{d.title}" was {decision}', link=f"/deals/{d.pk}/")


def moderator_remove(actor, kind, obj_id, reason):
    assert_moderator(actor)
    if len(reason.strip()) < 5:
        raise invalid("Give a reason (at least 5 characters).")
    _remove_content(kind, obj_id)
    audit(actor, f"{kind}.remove", kind, obj_id, {"reason": reason})


def resolve_dispute(actor, gig_id, outcome, note):
    assert_moderator(actor)
    if outcome not in {"completed", "cancelled"}:
        raise invalid("Invalid outcome.")
    gig = Gig.objects.filter(pk=gig_id, status="disputed").first()
    if not gig:
        raise conflict("This gig isn't in dispute.")
    gig.status = outcome
    gig.completed_at = timezone.now() if outcome == "completed" else None
    gig.cancel_reason = note if outcome == "cancelled" else ""
    gig.save()
    audit(actor, f"gig.dispute_{outcome}", "gig", gig.pk, {"note": note})
    for u in filter(None, [gig.poster, gig.assignee]):
        notify(u, "gig.dispute_resolved", f'Dispute on "{gig.title}" resolved: {outcome}', note, f"/gigs/{gig.pk}/")


# ------------------------------------------------------------------ campuses & categories
def create_institution(actor, *, name, short_name, city, type):
    assert_admin(actor)
    slug = slugify(short_name)
    if Institution.objects.filter(slug=slug).exists():
        raise conflict("An institution with that short name already exists.")
    i = Institution.objects.create(name=name, short_name=short_name.upper(), slug=slug, city=city, type=type)
    audit(actor, "institution.create", "institution", i.pk)
    return i


def create_campus(actor, *, institution_id, name, area):
    assert_admin(actor)
    inst = Institution.objects.filter(pk=institution_id).first()
    if not inst:
        raise not_found("That institution")
    slug = slugify(f"{inst.short_name}-{name}")
    if Campus.objects.filter(slug=slug).exists():
        raise conflict("That campus already exists.")
    c = Campus.objects.create(institution=inst, name=name, area=area, slug=slug)
    audit(actor, "campus.create", "campus", c.pk)
    return c


def set_campus_active(actor, campus_id, active):
    assert_admin(actor)
    Campus.objects.filter(pk=campus_id).update(is_active=active)
    audit(actor, "campus.activate" if active else "campus.deactivate", "campus", campus_id)


def create_category(actor, *, module, name, icon):
    assert_admin(actor)
    slug = slugify(name)
    if Category.objects.filter(module=module, slug=slug).exists():
        raise conflict("That category already exists.")
    c = Category.objects.create(module=module, name=name, slug=slug, icon=icon, sort_order=100)
    audit(actor, "category.create", "category", c.pk)


def set_category_active(actor, category_id, active):
    assert_admin(actor)
    Category.objects.filter(pk=category_id).update(is_active=active)
    audit(actor, "category.activate" if active else "category.deactivate", "category", category_id)


# ------------------------------------------------------------------ analytics
def platform_metrics(actor, *, days=30, include_sample=False):
    """
    Calculated from records only. GMV is value exchanged between users, not
    CampusHub revenue; revenue counts only collected fees; accrued fees are
    shown separately. Sample/test records are excluded unless requested.
    """
    assert_staff(actor)
    since = timezone.now() - timedelta(days=days)
    real = Q() if include_sample else Q(is_sample=False)

    users = User.objects.exclude(status="deleted")
    if not include_sample:
        users = users.exclude(email__endswith="@campushub.test")
    u = users.aggregate(
        total=Count("id"),
        new=Count("id", filter=Q(date_joined__gte=since)),
        active=Count("id", filter=Q(last_seen_at__gte=since, status="active")),
        suspended=Count("id", filter=Q(status="suspended")),
    )
    listings = Listing.objects.filter(real).aggregate(
        active=Count("id", filter=Q(status="active")),
        created=Count("id", filter=Q(created_at__gte=since)),
        sold=Count("id", filter=Q(status="sold", sold_at__gte=since)),
    )
    sellers = Listing.objects.filter(real, status="active").values("seller").distinct().count()
    gigs = Gig.objects.filter(real).aggregate(
        open=Count("id", filter=Q(status="open")),
        posted=Count("id", filter=Q(created_at__gte=since)),
        completed=Count("id", filter=Q(status="completed", completed_at__gte=since)),
        disputed=Count("id", filter=Q(status="disputed")),
        engaged=Count("id", filter=Q(status__in=["assigned", "completed", "disputed"])),
    )
    biz = Business.objects.filter(real).aggregate(
        total=Count("id"), verified=Count("id", filter=Q(verification="verified")), pending=Count("id", filter=Q(verification="pending"))
    )
    deal_real = Q() if include_sample else Q(deal__is_sample=False)
    claims = DealClaim.objects.filter(deal_real).aggregate(
        claims=Count("id", filter=Q(created_at__gte=since)), redeemed=Count("id", filter=Q(redeemed_at__gte=since))
    )
    live_deals = Deal.objects.live().filter(real).count()

    tx = Transaction.objects.filter(status="completed")
    if not include_sample:
        tx = tx.filter(is_sample=False, is_test=False)
    period = tx.filter(completed_at__gte=since)
    money = period.aggregate(
        n=Count("id"),
        gmv=Sum("amount_ugx"),
        collected=Sum("fee_ugx", filter=Q(fee_status="collected")),
        accrued=Sum("fee_ugx", filter=Q(fee_status="accrued")),
    )
    buyers = tx.exclude(buyer=None).values("buyer").annotate(n=Count("id"))
    gmv, collected = money["gmv"] or 0, money["collected"] or 0

    start = timezone.localdate() - timedelta(days=13)
    def per_day(qs, field):
        rows = qs.filter(**{f"{field}__date__gte": start}).annotate(d=TruncDate(field)).values("d").annotate(n=Count("id"))
        return {r["d"]: r["n"] for r in rows}
    s_users = per_day(users, "date_joined")
    s_list = per_day(Listing.objects.filter(real), "created_at")
    s_gigs = per_day(Gig.objects.filter(real), "created_at")
    daily = []
    for i in range(14):
        d = start + timedelta(days=i)
        daily.append({"day": d, "signups": s_users.get(d, 0), "listings": s_list.get(d, 0), "gigs": s_gigs.get(d, 0)})
    # Stacked bar geometry for the 14-day chart (SVG units: 120 high, bars 28 wide every 40).
    peak = max([1] + [x["signups"] + x["listings"] + x["gigs"] for x in daily])
    for i, x in enumerate(daily):
        h_s, h_l, h_g = (round(x[k] / peak * 120) for k in ("signups", "listings", "gigs"))
        x.update(x_pos=6 + i * 40, label_x=20 + i * 40, h_s=h_s, h_l=h_l, h_g=h_g,
                 y_sign=128 - h_s, y_list=128 - h_s - h_l, y_gig=128 - h_s - h_l - h_g)

    return {
        "days": days,
        "include_sample": include_sample,
        "users": u,
        "listings": {**listings, "sellers": sellers},
        "gigs": {**gigs, "dispute_rate": gigs["disputed"] / gigs["engaged"] if gigs["engaged"] else None},
        "biz": {**biz, **claims, "live_deals": live_deals},
        "money": {
            "transactions": money["n"],
            "gmv": gmv,
            "collected": collected,
            "accrued": money["accrued"] or 0,
            "take_rate": collected / gmv if gmv else None,
            "repeat_rate": (sum(1 for b in buyers if b["n"] >= 2) / len(buyers)) if buyers else None,
        },
        "open_reports": Report.objects.filter(status="open").count(),
        "daily": daily,
    }

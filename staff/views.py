"""
Staff dashboard. Pages require a staff role; every POST goes through
`act`, which dispatches to a service function that re-checks permissions.
"""

import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.icons import ICONS
from core.models import AuditLog, Category, Institution
from core.settings_store import CommissionSettings, get_commissions, save_commissions
from core.utils import AppError, assert_admin, invalid
from core.web import back, staff_required
from deals.models import Business, Deal
from gigs.models import Gig
from payments.models import Transaction

from . import services as s


@staff_required
def overview(request):
    days = int(request.GET.get("days", 30)) if request.GET.get("days") in {"7", "30", "90"} else 30
    m = s.platform_metrics(request.user, days=days, include_sample=request.GET.get("samples") == "1")
    return render(request, "staff/overview.html", {"m": m, "days": days})


@staff_required
def reports(request):
    status = request.GET.get("status") if request.GET.get("status") in {"open", "actioned", "dismissed"} else "open"
    return render(request, "staff/reports.html", {
        "rows": s.list_reports(request.user, status), "status": status,
        "disputes": Gig.objects.filter(status="disputed").order_by("-updated_at") if status == "open" else [],
    })


@staff_required
def users(request):
    qs = s.list_users(request.user, q=request.GET.get("q", "")[:80], status=request.GET.get("status", ""))
    return render(request, "staff/users.html", {"page": Paginator(qs, 30).get_page(request.GET.get("page"))})


@staff_required
def businesses(request):
    v = request.GET.get("v", "")
    qs = Business.objects.select_related("owner").order_by("-created_at")
    if v in Business.Verification.values:
        qs = qs.filter(verification=v)
    rows = sorted(qs[:200], key=lambda b: b.verification != "pending")
    return render(request, "staff/businesses.html", {"rows": rows, "v": v, "filters": ["", *Business.Verification.values]})


@staff_required
def deals(request):
    st = request.GET.get("status", "")
    qs = Deal.objects.select_related("business").order_by("-created_at")
    if st in Deal.Status.values:
        qs = qs.filter(status=st)
    rows = sorted(qs[:200], key=lambda d: d.status != "pending_review")
    return render(request, "staff/deals.html", {"rows": rows, "status": st, "filters": ["", *Deal.Status.values]})


@staff_required
def transactions(request):
    mod = request.GET.get("module", "")
    qs = Transaction.objects.select_related("seller", "buyer")
    if mod in Transaction.Module.values:
        qs = qs.filter(module=mod)
    return render(request, "staff/transactions.html", {"page": Paginator(qs, 50).get_page(request.GET.get("page")), "module": mod})


@staff_required
def campuses(request):
    insts = Institution.objects.prefetch_related("campuses").order_by("name")
    return render(request, "staff/campuses.html", {"insts": insts})


@staff_required
def categories(request):
    return render(request, "staff/categories.html", {"cats": Category.objects.all(), "icons": sorted(ICONS)})


@staff_required
def platform_settings(request):
    if not request.user.is_platform_admin:
        return redirect("staff:overview")
    from django.conf import settings

    return render(request, "staff/settings.html", {"c": get_commissions(), "provider": settings.PAYMENT_PROVIDER})


@staff_required
def audit_log(request):
    if not request.user.is_platform_admin:
        return redirect("staff:overview")
    return render(request, "staff/audit.html", {"rows": AuditLog.objects.select_related("actor")[:100]})


# ------------------------------------------------------------------ actions
def _uuid(v):
    try:
        return uuid.UUID(str(v))
    except ValueError:
        raise invalid("Invalid id.")


def _pct(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise invalid("Rates must be numbers.")
    if not 0 <= n <= 50:
        raise invalid("Rates must be between 0% and 50%.")
    return round(n * 100)  # percent -> basis points


def _commissions(u, p):
    assert_admin(u)
    save_commissions(u, CommissionSettings(enabled=p.get("enabled") == "on", rates={"marketplace": _pct(p.get("marketplace")), "gigs": _pct(p.get("gigs"))}))


OPS = {
    "resolve_report": (lambda u, p: s.resolve_report(u, _uuid(p["id"]), outcome=p.get("outcome"), note=p.get("note", "")), "Report resolved."),
    "resolve_dispute": (lambda u, p: s.resolve_dispute(u, _uuid(p["id"]), p.get("outcome"), p.get("note", "")), "Dispute resolved."),
    "suspend_user": (lambda u, p: s.suspend_user(u, _uuid(p["id"]), p.get("reason", "")), "User suspended and signed out."),
    "restore_user": (lambda u, p: s.restore_user(u, _uuid(p["id"])), "User restored."),
    "set_role": (lambda u, p: s.set_role(u, _uuid(p["id"]), p.get("role"), p.get("grant") == "1"), "Role updated."),
    "student_verify": (lambda u, p: s.set_student_verified(u, _uuid(p["id"]), p.get("verified") == "1"), "Student verification updated."),
    "business_verify": (lambda u, p: s.set_business_verification(u, _uuid(p["id"]), "verified" if p.get("decision") == "verified" else "rejected", p.get("note", "")), "Business verification updated."),
    "business_suspend": (lambda u, p: s.set_business_suspended(u, _uuid(p["id"]), p.get("suspended") == "1"), "Business status updated."),
    "moderate_deal": (lambda u, p: s.moderate_deal(u, _uuid(p["id"]), p.get("decision")), "Deal updated."),
    "remove_content": (lambda u, p: s.moderator_remove(u, "gig" if p.get("kind") == "gig" else "listing", _uuid(p["id"]), p.get("reason", "")), "Content removed."),
    "create_institution": (lambda u, p: s.create_institution(u, name=p.get("name", "").strip()[:120], short_name=p.get("short_name", "").strip()[:12],
                                                               city=p.get("city", "").strip()[:60], type=p.get("type", "university")), "Institution added."),
    "create_campus": (lambda u, p: s.create_campus(u, institution_id=_uuid_or_int(p.get("institution")), name=p.get("name", "").strip()[:80],
                                                   area=p.get("area", "").strip()[:120]), "Campus added."),
    "campus_active": (lambda u, p: s.set_campus_active(u, int(p["id"]), p.get("active") == "1"), "Campus updated."),
    "create_category": (lambda u, p: s.create_category(u, module="gigs" if p.get("module") == "gigs" else "marketplace",
                                                       name=p.get("name", "").strip()[:60], icon=p.get("icon") if p.get("icon") in ICONS else "package"), "Category added."),
    "category_active": (lambda u, p: s.set_category_active(u, int(p["id"]), p.get("active") == "1"), "Category updated."),
    "commissions": (_commissions, "Commission settings saved and recorded in the audit log."),
}


def _uuid_or_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        raise invalid("Choose an institution.")


@require_POST
@staff_required
def act(request, op):
    entry = OPS.get(op)
    if not entry:
        messages.error(request, "Unknown action.")
        return redirect(back(request, "/staff/"))
    fn, ok = entry
    p = request.POST
    try:
        for k in ("name", "short_name", "city", "area"):
            if k in p and op.startswith("create_") and len(p[k].strip()) < 2:
                raise invalid("Please fill in all fields.")
        fn(request.user, p)
        messages.success(request, ok)
    except (AppError, KeyError, ValueError) as e:
        messages.error(request, getattr(e, "message", "Invalid request."))
    return redirect(back(request, "/staff/"))

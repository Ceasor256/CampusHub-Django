from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from core.utils import AppError, throttle
from core.web import active_campuses, browse_campus, form_error, member_required, or_404, post_action

from . import services
from .forms import BusinessForm, DealForm, RedeemForm, VerificationForm
from .models import Business, DealClaim


def browse(request):
    campus = browse_campus(request)
    return render(request, "deals/browse.html", {"deals": services.live_deals(campus=campus), "campus": campus, "campuses": active_campuses()})


def detail(request, deal_id):
    user = request.user
    deal, is_owner = or_404(services.get_deal, deal_id, user)
    if not is_owner:
        services.increment_views(deal)
    return render(request, "deals/detail.html", {
        "d": deal, "is_owner": is_owner,
        "claim": DealClaim.objects.filter(deal=deal, user=user).first() if user.is_authenticated else None,
        "campus_mismatch": user.is_authenticated and deal.campus_id and deal.campus_id != user.campus_id,
    })


@post_action
def claim(request, deal_id):
    throttle(request, f"claim:{request.user.pk}", 30, 3600)
    services.claim(request.user, deal_id)
    messages.success(request, "Deal claimed! Show your code at the counter.")
    return redirect("deals:detail", deal_id)


def business_public(request, slug):
    b = or_404(services.business_for_viewer, slug[:90], request.user)
    return render(request, "deals/business_public.html", {"b": b, "deals": services.live_deals(business=b)})


def business_home(request):
    user = request.user
    form = BusinessForm(request.POST or None)
    if request.method == "POST":
        if not user.is_authenticated:
            return redirect("/login/?next=/business/")
        try:
            throttle(request, f"biz:{user.pk}", 5, 3600)
            if form.is_valid():
                b = services.create_business(user, form.cleaned_data)
                messages.success(request, "Business profile created. Next: request verification so your deals go live instantly.")
                return redirect("deals:dashboard", b.pk)
        except AppError as e:
            form_error(form, e)
    mine = Business.objects.filter(owner=user) if user.is_authenticated else []
    return render(request, "deals/business_home.html", {"form": form, "mine": mine})


@member_required
def dashboard(request, business_id):
    b, deals = or_404(services.dashboard, request.user, business_id)
    form = BusinessForm(request.POST or None, initial={k: getattr(b, k) for k in ("name", "kind", "description", "address", "phone", "email")})
    if request.method == "POST":
        try:
            if form.is_valid():
                services.update_business(request.user, b.pk, form.cleaned_data)
                messages.success(request, "Business profile saved.")
                return redirect("deals:dashboard", b.pk)
        except AppError as e:
            form_error(form, e)
    totals = {
        "views": sum(d.view_count for d in deals),
        "claims": sum(d.claim_count for d in deals),
        "redeemed": sum(d.redeemed for d in deals),
    }
    totals["rate"] = round(totals["redeemed"] / totals["claims"] * 100) if totals["claims"] else None
    return render(request, "deals/dashboard.html", {"b": b, "deals": deals, "totals": totals, "form": form, "now": timezone.now(),
                                                     "verify_form": VerificationForm(), "redeem_form": RedeemForm()})


@member_required
def new_deal(request, business_id):
    b = or_404(services.owned_business, request.user, business_id)
    form = DealForm(request.POST or None)
    if request.method == "POST":
        try:
            throttle(request, f"deal:{request.user.pk}", 20, 3600)
            if form.is_valid():
                d = services.create_deal(request.user, b.pk, form.cleaned_data)
                messages.success(request, "Deal published." if d.status == "active" else "Deal submitted for review. We'll notify you when it's approved.")
                return redirect("deals:dashboard", b.pk)
        except AppError as e:
            form_error(form, e)
    return render(request, "deals/deal_form.html", {"b": b, "form": form, "campuses": active_campuses()})


@post_action
def request_verification(request, business_id):
    form = VerificationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Tell us how to verify you (at least 20 characters).")
    else:
        services.request_verification(request.user, business_id, form.cleaned_data["note"])
        messages.success(request, "Verification requested. Our team usually responds within 2 working days.")
    return redirect("deals:dashboard", business_id)


@post_action
def redeem(request, business_id):
    throttle(request, f"redeem:{request.user.pk}", 60, 600)
    c = services.redeem(request.user, business_id, request.POST.get("code", ""))
    messages.success(request, f"✓ Valid. Redeemed “{c.deal.title}” for {c.user.full_name}.")
    return redirect("deals:dashboard", business_id)


@post_action
def pause_deal(request, business_id, deal_id):
    paused = request.POST.get("paused") == "1"
    services.set_paused_by_owner(request.user, deal_id, paused)
    messages.success(request, "Deal paused." if paused else "Deal resumed.")
    return redirect("deals:dashboard", business_id)

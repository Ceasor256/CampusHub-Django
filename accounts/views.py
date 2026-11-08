from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.utils import AppError, throttle
from core.web import form_error, member_required, safe_next
from deals.models import Business, DealClaim
from gigs.models import Gig, GigApplication
from marketplace.models import Favourite, Listing
from marketplace.services import card_queryset
from payments.models import Transaction

from . import services
from .forms import DeleteAccountForm, ForgotForm, LoginForm, OnboardingForm, ProfileForm, RegisterForm, ResetForm

User = get_user_model()


def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        try:
            throttle(request, "register", 5, 600)
            if form.is_valid():
                d = form.cleaned_data
                user = services.register_user(full_name=d["full_name"], email=d["email"], phone=d["phone"], password=d["password"])
                services.send_verification_email(user)
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                return redirect(f"/onboarding/?next={safe_next(request)}")
        except AppError as e:
            form_error(form, e)
    return render(request, "accounts/register.html", {"form": form, "next": safe_next(request)})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(safe_next(request))
    form = LoginForm(request.POST or None)
    if request.method == "POST":
        try:
            throttle(request, "login", 10, 900)
            if form.is_valid():
                user = authenticate(request, email=form.cleaned_data["email"].lower(), password=form.cleaned_data["password"])
                if user is None or user.status == "deleted":
                    form.add_error(None, "Email or password is incorrect.")
                else:
                    login(request, user)  # rotates the session key
                    return redirect(safe_next(request))
        except AppError as e:
            form_error(form, e)
    return render(request, "accounts/login.html", {"form": form, "next": safe_next(request)})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:home")


def forgot_password(request):
    form = ForgotForm(request.POST or None)
    sent = False
    if request.method == "POST":
        try:
            throttle(request, "forgot", 5, 900)
            if form.is_valid():
                services.send_password_reset(form.cleaned_data["email"])
                sent = True  # same answer either way: no account discovery
        except AppError as e:
            form_error(form, e)
    return render(request, "accounts/forgot.html", {"form": form, "sent": sent})


def reset_password(request, uidb64, token):
    user = services.user_from_reset_link(uidb64, token)
    if not user:
        return render(request, "accounts/reset.html", {"invalid": True})
    form = ResetForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.reset_password(user, form.cleaned_data["password"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Password changed. You've been signed out of other devices.")
        return redirect("accounts:me")
    return render(request, "accounts/reset.html", {"form": form})


def verify_email(request, token):
    """A button press (POST) confirms, so email link scanners can't consume the token."""
    if request.method == "POST":
        try:
            services.verify_email(token)
            messages.success(request, "Email confirmed ✓")
            return redirect("accounts:me" if request.user.is_authenticated else "accounts:login")
        except AppError as e:
            return render(request, "accounts/verify.html", {"error": e.message})
    return render(request, "accounts/verify.html", {})


@require_POST
@member_required
def resend_verification(request):
    try:
        throttle(request, f"resend:{request.user.pk}", 3, 3600)
        if request.user.email_verified_at:
            messages.info(request, "Your email is already confirmed.")
        else:
            services.send_verification_email(request.user)
            messages.success(request, f"Verification email sent to {request.user.email}.")
    except AppError as e:
        messages.error(request, e.message)
    return redirect("accounts:me")


def onboarding(request):
    if not request.user.is_authenticated:
        return redirect(f"/login/?next=/onboarding/")
    form = OnboardingForm(request.POST or None, initial={"phone": request.user.phone})
    if request.method == "POST" and form.is_valid():
        try:
            services.complete_onboarding(request.user, campus_id=form.cleaned_data["campus"].pk, phone=form.cleaned_data["phone"])
            return redirect(safe_next(request))
        except AppError as e:
            form_error(form, e)
    return render(request, "accounts/onboarding.html", {"form": form, "next": safe_next(request)})


ME_TABS = [("listings", "My listings", "store"), ("gigs", "My gigs", "briefcase"), ("saved", "Saved", "heart"),
           ("deals", "My deals", "tag"), ("purchases", "Purchases", "package")]


@member_required
def me(request):
    u = request.user
    tab = request.GET.get("tab") if request.GET.get("tab") in dict((t[0], 1) for t in ME_TABS) else "listings"
    ctx = {"tab": tab, "tabs": ME_TABS, "now": timezone.now(), "rating": services.rating_summary(u), "businesses": Business.objects.filter(owner=u)}
    if tab == "listings":
        ctx["listings"] = card_queryset().filter(seller=u).exclude(status="removed")
    elif tab == "gigs":
        from gigs.services import card_queryset as gig_cards

        ctx["posted"] = gig_cards().filter(poster=u).exclude(status="removed")
        ctx["applied"] = GigApplication.objects.filter(applicant=u).exclude(gig__status="removed").select_related("gig")
    elif tab == "saved":
        ids = Favourite.objects.filter(user=u).values("listing_id")
        ctx["listings"] = card_queryset().filter(pk__in=ids, status__in=["active", "sold"])
    elif tab == "deals":
        ctx["claims"] = DealClaim.objects.filter(user=u).select_related("deal__business")
    else:
        txs = list(Transaction.objects.filter(reference_type="listing", buyer=u).select_related("seller"))
        titles = dict(Listing.objects.filter(pk__in=[t.reference_id for t in txs]).values_list("pk", "title"))
        ctx["purchases"] = [{"t": t, "title": titles.get(t.reference_id, "(removed)")} for t in txs]
    return render(request, "accounts/me.html", ctx)


@member_required
def settings_view(request):
    u = request.user
    form = ProfileForm(request.POST or None, initial={"full_name": u.full_name, "campus": u.campus, "phone": u.phone, "bio": u.bio})
    if request.method == "POST" and form.is_valid():
        try:
            d = form.cleaned_data
            services.update_profile(u, full_name=d["full_name"], phone=d["phone"], bio=d["bio"], campus_id=d["campus"].pk)
            messages.success(request, "Profile saved.")
            return redirect("accounts:settings")
        except AppError as e:
            form_error(form, e)
    return render(request, "accounts/settings.html", {"form": form, "delete_form": DeleteAccountForm()})


@require_POST
@member_required
def delete_account(request):
    form = DeleteAccountForm(request.POST)
    if form.is_valid():
        try:
            throttle(request, f"delete:{request.user.pk}", 5, 3600)
            services.delete_account(request.user, form.cleaned_data["password"])
            logout(request)
            messages.success(request, "Your account has been deleted.")
            return redirect("core:home")
        except AppError as e:
            form_error(form, e)
    u = request.user
    profile = ProfileForm(initial={"full_name": u.full_name, "campus": u.campus, "phone": u.phone, "bio": u.bio})
    return render(request, "accounts/settings.html", {"form": profile, "delete_form": form})


def profile(request, user_id):
    u = get_object_or_404(User.objects.select_related("campus__institution").exclude(status="deleted"), pk=user_id)
    from core.models import Review

    return render(request, "accounts/profile.html", {
        "profile": u,
        "rating": services.rating_summary(u),
        "listings": card_queryset().filter(seller=u, status="active")[:24],
        "reviews": Review.objects.filter(reviewee=u).select_related("reviewer")[:10],
    })

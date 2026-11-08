from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from core.forms import MessageForm
from core.models import Category, Review
from core.utils import AppError, throttle
from core.web import active_campuses, browse_campus, form_error, member_required, or_404, post_action

from . import services
from .forms import ApplicationForm, GigForm, ReviewForm
from .models import GigApplication


def browse(request):
    campus = browse_campus(request)
    g = request.GET
    qs = services.search(q=g.get("q", ""), campus=campus, category=g.get("category", ""), mode=g.get("mode", ""))
    return render(request, "gigs/browse.html", {
        "page": Paginator(qs, 20).get_page(g.get("page")), "campus": campus, "campuses": active_campuses(),
        "categories": Category.objects.filter(module="gigs", is_active=True),
    })


@member_required
def create(request):
    form = GigForm(request.POST or None, initial={"campus": request.user.campus})
    if request.method == "POST":
        try:
            throttle(request, f"gig:{request.user.pk}", 10, 3600)
            if form.is_valid():
                gig = services.create_gig(request.user, form.cleaned_data)
                messages.success(request, "Your gig is live! You'll be notified when someone applies.")
                return redirect("gigs:detail", gig.pk)
        except AppError as e:
            form_error(form, e)
    return render(request, "gigs/form.html", {"form": form})


def detail(request, gig_id, apply_form=None):
    user = request.user
    gig = or_404(services.get_gig, gig_id, user)
    authed = user.is_authenticated
    is_poster = authed and gig.poster_id == user.pk
    is_assignee = authed and gig.assignee_id == user.pk
    ctx = {
        "g": gig, "is_poster": is_poster, "is_assignee": is_assignee,
        "applications": gig.applications.exclude(status="withdrawn").select_related("applicant") if (is_poster or (authed and user.can_moderate)) else [],
        "my_app": GigApplication.objects.filter(gig=gig, applicant=user).exclude(status="withdrawn").first() if authed else None,
        "has_reviewed": authed and Review.objects.filter(reviewer=user, context_type="gig", context_id=gig.pk).exists(),
        "i_confirmed": (is_poster and gig.poster_confirmed_at) or (is_assignee and gig.worker_confirmed_at),
        "apply_form": apply_form or ApplicationForm(initial={"proposed_ugx": gig.budget_ugx}),
        "message_form": MessageForm(),
        "steps": ["Open for applications", "Provider assigned", "Completed"],
        "step": {"open": 0, "assigned": 1, "completed": 2}.get(gig.status, -1),
    }
    return render(request, "gigs/detail.html", ctx)


@member_required
def apply(request, gig_id):
    if request.method != "POST":
        return redirect("gigs:detail", gig_id)
    form = ApplicationForm(request.POST)
    try:
        throttle(request, f"apply:{request.user.pk}", 30, 3600)
        if form.is_valid():
            services.apply(request.user, gig_id, **form.cleaned_data)
            messages.success(request, "Application sent! You'll get a notification when the poster responds.")
            return redirect("gigs:detail", gig_id)
    except AppError as e:
        form_error(form, e)
    return detail(request, gig_id, apply_form=form)


@post_action
def withdraw(request, gig_id):
    services.withdraw(request.user, gig_id)
    messages.success(request, "Application withdrawn.")
    return redirect("gigs:detail", gig_id)


@post_action
def accept(request, gig_id, application_id):
    services.accept(request.user, application_id)
    messages.success(request, "Provider selected. Message them to agree on the details.")
    return redirect("gigs:detail", gig_id)


@post_action
def confirm(request, gig_id):
    r = services.confirm_completion(request.user, gig_id)
    messages.success(request, "Gig completed! Please leave a review." if r == "completed" else "Confirmed. Waiting for the other person to confirm.")
    return redirect("gigs:detail", gig_id)


@post_action
def cancel(request, gig_id):
    services.cancel(request.user, gig_id, request.POST.get("reason", "").strip())
    messages.success(request, "Gig cancelled. Applicants have been notified.")
    return redirect("gigs:detail", gig_id)


@post_action
def dispute(request, gig_id):
    services.dispute(request.user, gig_id, request.POST.get("details", ""))
    messages.success(request, "Dispute opened. A moderator will contact you both.")
    return redirect("gigs:detail", gig_id)


@post_action
def review(request, gig_id):
    form = ReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a rating from 1 to 5.")
        return redirect("gigs:detail", gig_id)
    services.review(request.user, gig_id, **form.cleaned_data)
    messages.success(request, "Thanks for your review!")
    return redirect("gigs:detail", gig_id)

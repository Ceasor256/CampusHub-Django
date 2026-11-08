from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import ReportForm
from core.models import Category, EmailOutbox
from core.utils import AppError, throttle
from core.web import CAMPUS_COOKIE, active_campuses, back, browse_campus, member_required, post_action
from deals.services import live_deals
from gigs.services import search as search_gigs
from marketplace.services import search as search_listings

COMING_SOON = [("utensils", "Food delivery"), ("printer", "Printing"), ("building-2", "Hostels"),
               ("calendar-days", "Events & tickets"), ("graduation-cap", "Tutoring"), ("briefcase", "Student jobs")]


def home(request):
    campus = browse_campus(request)
    return render(request, "core/home.html", {
        "campus": campus,
        "campuses": active_campuses(),
        "categories": Category.objects.filter(module="marketplace", is_active=True),
        "listings": search_listings(campus=campus)[:8],
        "gigs": search_gigs(campus=campus)[:4],
        "deals": live_deals(campus=campus)[:4],
        "coming_soon": COMING_SOON,
    })


@require_POST
def set_campus(request):
    slug = (request.POST.get("campus") or "all")[:80]
    resp = redirect(back(request))
    if slug.replace("-", "").isalnum():
        resp.set_cookie(CAMPUS_COOKIE, slug, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax", secure=request.is_secure())
    return resp


SERVICES = [
    ("store", "Marketplace", "Buy and sell with students on your campus.", "/marketplace/", "live"),
    ("briefcase", "Gigs & tasks", "Post tasks, apply, get chosen and get paid.", "/gigs/", "live"),
    ("tag", "Campus deals", "Discounts from verified local businesses.", "/deals/", "live"),
    ("wrench", "Student services", "Photography, design, repairs, barbering and more. For now, post or find these as gigs.", "/gigs/", "live"),
    ("utensils", "Food & delivery", "Order from restaurants and campus food vendors.", None, "next"),
    ("printer", "Printing & photocopying", "Upload documents securely and collect from partner print shops.", None, "next"),
    ("building-2", "Hostels & accommodation", "Find verified rooms near campus and request viewings.", None, "next"),
    ("calendar-days", "Events & tickets", "Discover campus events and buy tickets with QR verification.", None, "later"),
    ("graduation-cap", "Tutoring", "Book sessions with tutors by subject.", None, "later"),
    ("sparkles", "Student jobs", "Part-time and short-term work. Never pay to apply for a job.", None, "later"),
    ("crown", "CampusHub Premium", "Exclusive deals and lower fees for members.", None, "later"),
]


def services(request):
    return render(request, "core/services.html", {"modules": SERVICES})


def sell(request):
    return render(request, "core/sell.html")


def page(template):
    def view(request):
        return render(request, template)

    return view


@post_action
def report(request):
    from staff.services import create_report

    form = ReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a reason for your report.")
        return redirect(back(request))
    throttle(request, f"report:{request.user.pk}", 20, 3600)
    create_report(request.user, **form.cleaned_data)
    messages.success(request, "Thanks. Our moderators will review this report. You won't be identified to the other person.")
    return redirect(back(request))


@member_required
def notifications(request):
    if request.method == "POST":
        request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
        return redirect("core:notifications")
    return render(request, "core/notifications.html", {"items": request.user.notifications.all()[:100]})


def dev_outbox(request):
    if not settings.DEBUG or settings.EMAIL_BACKEND != "core.mail.OutboxBackend":
        raise Http404
    return render(request, "core/outbox.html", {"mails": EmailOutbox.objects.all()[:30]})


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)

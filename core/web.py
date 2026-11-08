"""View helpers: auth decorators, safe redirects, error handling, campus selection."""

from functools import wraps

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.models import Campus
from core.utils import AppError

CAMPUS_COOKIE = "ch_campus"


def safe_next(request, fallback="/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return fallback


def back(request, fallback="/"):
    ref = request.META.get("HTTP_REFERER", "")
    if ref and url_has_allowed_host_and_scheme(ref, allowed_hosts={request.get_host()}):
        return ref
    return fallback


def member_required(view):
    """Signed in and onboarded (campus chosen). Suspended users may still view."""

    @wraps(view)
    def wrapper(request, *a, **kw):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.get_full_path()}")
        if not request.user.onboarded_at:
            return redirect(f"{reverse('accounts:onboarding')}?next={request.get_full_path()}")
        return view(request, *a, **kw)

    return wrapper


def staff_required(view):
    @wraps(view)
    @member_required
    def wrapper(request, *a, **kw):
        if not request.user.is_staff_member:
            return redirect("core:home")
        return view(request, *a, **kw)

    return wrapper


def post_action(view):
    """
    POST-only action: runs the view, shows AppError messages as flash errors
    and returns the user to where they came from.
    """

    @wraps(view)
    @require_POST
    @member_required
    def wrapper(request, *a, **kw):
        try:
            return view(request, *a, **kw)
        except AppError as e:
            if e.code == "not_found":
                raise Http404(e.message)
            messages.error(request, e.message)
            return redirect(back(request))

    return wrapper


def or_404(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except AppError as e:
        if e.code in ("not_found", "forbidden"):
            raise Http404(e.message)
        raise


def form_error(form, e: AppError):
    """Attach a service-layer error to a bound form."""
    form.add_error(None, e.message)


def browse_campus(request):
    """?campus= query > cookie > the user's campus > all campuses. Returns (campus|None, slug)."""
    pref = request.GET.get("campus") or request.COOKIES.get(CAMPUS_COOKIE)
    if pref == "all":
        return None
    if pref:
        c = Campus.objects.filter(slug=pref, is_active=True).select_related("institution").first()
        if c:
            return c
    u = request.user
    if u.is_authenticated and u.campus_id:
        return Campus.objects.select_related("institution").filter(pk=u.campus_id).first()
    return None


def active_campuses():
    return Campus.objects.filter(is_active=True, institution__is_active=True).select_related("institution")

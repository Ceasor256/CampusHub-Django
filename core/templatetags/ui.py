"""
CampusHub template helpers (registered as builtins, no {% load %} needed).

    {% icon "store" "size-5" %}        inline Lucide SVG
    {{ amount|ugx }}                   UGX 1,250,000
    {% status_badge obj.status %}      coloured badge
    {% sample_badge obj.is_sample %}
    {% avatar user.full_name "md" %}
    {% querystring_set request "page" 2 %}
"""

import hashlib

from django import template
from django.utils import dateformat, timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from core.icons import ICONS
from core.utils import bps_to_percent, format_ug_phone, format_ugx, format_ugx_short

register = template.Library()


@register.simple_tag
def icon(name, cls="size-5", label=""):
    nodes = ICONS.get(name) or ICONS["package"]
    inner = mark_safe(
        "".join(
            format_html("<{} {}/>", tag, format_html_join(" ", '{}="{}"', ((k, v) for k, v in attrs.items())))
            for tag, attrs in nodes
        )
    )
    aria = format_html('role="img" aria-label="{}"', label) if label else mark_safe('aria-hidden="true"')
    return format_html(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" class="{}" {}>{}</svg>',
        cls,
        aria,
        inner,
    )


@register.filter
def ugx(amount):
    return format_ugx(amount)


@register.filter
def ugx_price(amount):
    return "Free" if amount == 0 else format_ugx(amount)


@register.filter
def ugx_short(amount):
    return format_ugx_short(int(amount or 0))


@register.filter
def percent_bps(bps):
    return bps_to_percent(int(bps or 0))


@register.filter
def pct(ratio):
    return "—" if ratio is None else f"{ratio * 100:.1f}%"


@register.filter
def phone(e164):
    return format_ug_phone(e164)


@register.filter
def ago(dt):
    if not dt:
        return ""
    s = int((timezone.now() - dt).total_seconds())
    if s < 60:
        return "just now"
    m = s // 60
    if m < 60:
        return f"{m}m ago"
    h = m // 60
    if h < 24:
        return f"{h}h ago"
    d = h // 24
    if d < 7:
        return f"{d}d ago"
    return dateformat.format(timezone.localtime(dt), "j M Y")


@register.filter
def stars(rating):
    r = int(rating or 0)
    return "★" * r + "☆" * (5 - r)


_TONE = {
    "active": "success", "open": "success", "verified": "success", "completed": "success", "succeeded": "success",
    "accepted": "success", "actioned": "success",
    "paused": "warning", "pending": "warning", "pending_review": "warning", "assigned": "info",
    "offline_unverified": "neutral", "sold": "brand", "redeemed": "brand",
    "cancelled": "neutral", "withdrawn": "neutral", "dismissed": "neutral", "unverified": "neutral", "expired": "neutral", "ended": "neutral",
    "removed": "danger", "rejected": "danger", "disputed": "danger", "suspended": "danger", "failed": "danger", "deleted": "danger",
}
_LABEL = {"pending_review": "In review", "offline_unverified": "Paid offline (unverified)", "rejected": "Not selected"}


@register.simple_tag
def status_badge(status, label=None):
    s = str(status)
    text = label or _LABEL.get(s) or s.replace("_", " ").capitalize()
    return format_html('<span class="badge badge-{}">{}</span>', _TONE.get(s, "neutral"), text)


@register.simple_tag
def sample_badge(is_sample):
    if not is_sample:
        return ""
    return mark_safe('<span class="badge badge-warning" title="Sample content for development. Not a real listing.">Sample</span>')


@register.simple_tag
def verified_badge(label="Verified"):
    return format_html('<span class="badge badge-info">{} {}</span>', icon("badge-check", "size-3.5"), label)


_AVATAR_TONES = ["bg-brand-100 text-brand-800", "bg-accent-100 text-accent-900", "bg-success-bg text-success", "bg-info-bg text-info", "bg-danger-bg text-danger"]
_AVATAR_SIZE = {"sm": "size-8 text-xs", "md": "size-10 text-sm", "lg": "size-16 text-xl"}


@register.simple_tag
def avatar(name, size="md"):
    name = name or "?"
    tone = _AVATAR_TONES[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(_AVATAR_TONES)]
    initials = "".join(p[0].upper() for p in name.split()[:2]) or "?"
    return format_html(
        '<span aria-hidden="true" class="inline-grid shrink-0 place-items-center rounded-full font-bold {} {}">{}</span>',
        tone,
        _AVATAR_SIZE.get(size, _AVATAR_SIZE["md"]),
        initials,
    )


@register.simple_tag
def querystring_set(request, key, value):
    """Current query string with one key replaced (for pagination and chips)."""
    q = request.GET.copy()
    if value in (None, ""):
        q.pop(key, None)
    else:
        q[key] = value
    if key != "page":
        q.pop("page", None)
    return "?" + q.urlencode()


@register.filter
def get_item(d, key):
    return d.get(key) if hasattr(d, "get") else None


@register.filter
def widget(bound_field):
    """Render a form field's widget with accessible error attributes."""
    attrs = {}
    if bound_field.errors:
        attrs = {"aria-invalid": "true", "aria-describedby": f"{bound_field.auto_id}-error"}
    return bound_field.as_widget(attrs=attrs)

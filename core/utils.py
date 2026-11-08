"""
Small, dependency-free helpers shared across CampusHub:
money (integer UGX), Ugandan phone numbers, permission errors, rate limiting,
audit logging and notifications.
"""

import re

from django.core.cache import cache

# ------------------------------------------------------------------ errors


class AppError(Exception):
    """An error that is safe to show to the user. `code` maps to HTTP-ish meaning."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def not_found(what="That item"):
    return AppError("not_found", f"{what} could not be found.")


def forbidden(msg="You don't have permission to do that."):
    return AppError("forbidden", msg)


def invalid(msg):
    return AppError("invalid", msg)


def conflict(msg):
    return AppError("conflict", msg)


# ------------------------------------------------------------------ permissions
# Every mutation in services.py calls one of these. Hiding UI is never the only guard.


def assert_active(user):
    if user is None or not user.is_authenticated:
        raise AppError("unauthenticated", "Please log in to continue.")
    if user.status == "suspended":
        raise forbidden("Your account is suspended. Contact support@campushub.ug to appeal.")
    if user.status != "active":
        raise forbidden()


def assert_staff(user):
    assert_active(user)
    if not user.is_staff_member:
        raise forbidden()


def assert_moderator(user):
    assert_active(user)
    if not user.can_moderate:
        raise forbidden()


def assert_admin(user):
    assert_active(user)
    if not user.is_platform_admin:
        raise forbidden()


# ------------------------------------------------------------------ money


def format_ugx(amount) -> str:
    if amount is None:
        return "—"
    return f"UGX {int(amount):,}"


def format_ugx_short(amount: int) -> str:
    if amount >= 1_000_000:
        return f"UGX {round(amount / 1_000_000, 1):g}M"
    if amount >= 1_000:
        return f"UGX {round(amount / 1_000, 1):g}K"
    return f"UGX {amount}"


def parse_ugx(value):
    """'1,250,000' / 'UGX 5000' -> int. Returns None for anything that isn't whole shillings."""
    if value is None:
        return None
    s = re.sub(r"[\s,_]", "", str(value))
    s = re.sub(r"^UGX", "", s, flags=re.I)
    return int(s) if s.isdigit() else None


def compute_fee(amount_ugx: int, rate_bps: int) -> int:
    """Fee in UGX at a rate in basis points (100 bps = 1%). Integer maths, round half up."""
    if not isinstance(amount_ugx, int) or amount_ugx < 0:
        raise ValueError("Invalid amount")
    if not isinstance(rate_bps, int) or not 0 <= rate_bps <= 10_000:
        raise ValueError("Invalid rate")
    return (amount_ugx * rate_bps + 5_000) // 10_000


def bps_to_percent(bps: int) -> str:
    return f"{bps / 100:g}%"


# ------------------------------------------------------------------ phone


def normalize_ug_phone(value: str):
    """
    Accepts 0772123456, 772123456, +256772123456, 256772123456 (spaces and
    dashes allowed) and returns E.164 (+256XXXXXXXXX), or None if invalid.
    """
    s = re.sub(r"[\s\-().]", "", value or "")
    national = None
    if re.fullmatch(r"\+256\d{9}", s):
        national = s[4:]
    elif re.fullmatch(r"256\d{9}", s):
        national = s[3:]
    elif re.fullmatch(r"0\d{9}", s):
        national = s[1:]
    elif re.fullmatch(r"\d{9}", s):
        national = s
    if not national or national[0] not in "2347":  # mobile 7xx, landline 2/3/4xx
        return None
    return "+256" + national


def format_ug_phone(e164: str) -> str:
    n = (e164 or "").removeprefix("+256")
    return f"+256 {n[:3]} {n[3:6]} {n[6:]}" if len(n) == 9 else e164


# ------------------------------------------------------------------ rate limiting


def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "local")


def throttle(request, key: str, limit: int, window_sec: int):
    """Fixed-window limiter backed by the Django cache (use Redis for multiple workers)."""
    cache_key = f"rl:{key}:{client_ip(request)}"
    added = cache.add(cache_key, 1, window_sec)
    count = 1 if added else cache.incr(cache_key)
    if count > limit:
        raise AppError("rate_limited", f"Too many attempts. Please wait {max(1, window_sec // 60)} minute(s) and try again.")


# ------------------------------------------------------------------ audit & notifications


def audit(actor, action, target_type="", target_id="", metadata=None, ip=None):
    from core.models import AuditLog

    AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        metadata=metadata or {},
        ip=ip,
    )


def notify(user, type, title, body="", link=""):
    """In-app notification. Email/SMS/push can fan out from here later."""
    from core.models import Notification

    Notification.objects.create(user=user, type=type, title=title[:200], body=(body or "")[:300], link=link)


# ------------------------------------------------------------------ academic integrity

_ACADEMIC_DISHONESTY = [
    re.compile(r"\b(do|write|take|sit|complete|answer)\s+(my|our|the)\s+(exam|test|quiz|cat|coursework|assignment|dissertation|thesis|research paper)s?\b", re.I),
    re.compile(r"\bexam\s+(impersonat|proxy|stand[- ]?in)", re.I),
    re.compile(r"\bpay\s+(someone|you)\s+to\s+(write|do)\b", re.I),
]


def looks_like_academic_dishonesty(text: str) -> bool:
    """First-line filter for gigs asking someone to complete graded work. Moderators handle the rest."""
    return any(p.search(text or "") for p in _ACADEMIC_DISHONESTY)

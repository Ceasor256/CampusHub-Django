from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone


class LastSeenMiddleware:
    """Records activity for monthly-active-user metrics, at most once an hour per user."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = timezone.now()
            if not user.last_seen_at or now - user.last_seen_at > timedelta(hours=1):
                get_user_model().objects.filter(pk=user.pk).update(last_seen_at=now)
        return self.get_response(request)

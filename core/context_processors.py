from django.conf import settings


def site(request):
    """Header counts for signed-in users (unread messages and notifications)."""
    ctx = {"DEBUG": settings.DEBUG, "unread_messages": 0, "unread_notifications": 0}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from messaging.services import unread_message_count

        ctx["unread_messages"] = unread_message_count(user)
        ctx["unread_notifications"] = user.notifications.filter(read_at__isnull=True).count()
    return ctx

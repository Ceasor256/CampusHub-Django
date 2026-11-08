from django.db import transaction
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery, Sum
from django.utils import timezone

from core.models import Notification
from core.utils import assert_active, forbidden, invalid, not_found, notify

from .models import Conversation, Message, Participant


@transaction.atomic
def start_conversation(user, *, recipient, body, listing=None, gig=None):
    assert_active(user)
    if recipient.pk == user.pk:
        raise invalid("You can't message yourself.")
    if recipient.status != "active":
        raise not_found("That user")
    subject = "direct"
    if listing is not None:
        if listing.status == "removed":
            raise not_found("That listing")
        if listing.seller_id not in (user.pk, recipient.pk):
            raise forbidden()
        subject = f"listing:{listing.pk}"
    elif gig is not None:
        if recipient.pk not in (gig.poster_id, gig.assignee_id) and user.pk != gig.poster_id:
            raise forbidden()
        subject = f"gig:{gig.pk}"
    pair = ":".join(sorted([str(user.pk), str(recipient.pk)]))
    conv, created = Conversation.objects.get_or_create(thread_key=f"{pair}:{subject}", defaults={"listing": listing, "gig": gig})
    if created:
        Participant.objects.bulk_create([Participant(conversation=conv, user=user), Participant(conversation=conv, user=recipient)])
    _insert(user, conv, body)
    return conv


def _insert(user, conv, body):
    now = timezone.now()
    Message.objects.create(conversation=conv, sender=user, body=body)
    Conversation.objects.filter(pk=conv.pk).update(last_message_at=now)
    Participant.objects.filter(conversation=conv, user=user).update(last_read_at=now)
    link = f"/messages/{conv.pk}/"
    for p in Participant.objects.filter(conversation=conv).exclude(user=user).select_related("user"):
        # One unread notification per thread is enough (avoid spamming).
        if not Notification.objects.filter(user=p.user, link=link, read_at__isnull=True).exists():
            notify(p.user, "message.new", f"New message from {user.full_name}", body[:120], link)


def _participant(user, conv_id):
    p = Participant.objects.filter(conversation_id=conv_id, user=user).select_related("conversation").first()
    if not p:
        raise not_found("That conversation")
    return p


@transaction.atomic
def send(user, conv_id, body):
    assert_active(user)
    _insert(user, _participant(user, conv_id).conversation, body)


def inbox(user):
    last = Message.objects.filter(conversation=OuterRef("pk")).order_by("-created_at")
    convs = (
        Conversation.objects.filter(participants__user=user)
        .select_related("listing", "gig")
        .prefetch_related(Prefetch("participants", queryset=Participant.objects.select_related("user")))
        .annotate(last_body=Subquery(last.values("body")[:1]))
        .order_by("-last_message_at")[:100]
    )
    unread = {p["conversation_id"]: p["n"] for p in _unread_per_conversation(user).values("conversation_id", "n")}
    out = []
    for c in convs:
        other = next((p.user for p in c.participants.all() if p.user_id != user.pk), None)
        out.append({"c": c, "other": other, "unread": unread.get(c.pk, 0)})
    return out


def open_conversation(user, conv_id):
    p = _participant(user, conv_id)
    conv = Conversation.objects.select_related("listing", "gig").get(pk=p.conversation_id)
    other = conv.participants.exclude(user=user).select_related("user").first()
    msgs = list(conv.messages.select_related("sender").order_by("created_at")[:500])
    Participant.objects.filter(pk=p.pk).update(last_read_at=timezone.now())
    Notification.objects.filter(user=user, link=f"/messages/{conv.pk}/", read_at__isnull=True).update(read_at=timezone.now())
    return conv, (other.user if other else None), msgs


def _unread_per_conversation(user):
    unread = ~Q(conversation__messages__sender=user) & (
        Q(last_read_at__isnull=True) | Q(conversation__messages__created_at__gt=F("last_read_at"))
    )
    return Participant.objects.filter(user=user).annotate(n=Count("conversation__messages", filter=unread))


def unread_message_count(user):
    return _unread_per_conversation(user).aggregate(total=Sum("n"))["total"] or 0

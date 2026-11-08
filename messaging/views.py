import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import redirect, render

from core.forms import MessageForm
from core.utils import AppError, throttle
from core.web import back, member_required, or_404, post_action
from gigs.models import Gig
from marketplace.models import Listing

from . import services

User = get_user_model()


def _uuid(v):
    try:
        return uuid.UUID(str(v)) if v else None
    except ValueError:
        return None


@member_required
def inbox(request):
    return render(request, "messaging/inbox.html", {"rows": services.inbox(request.user)})


@member_required
def conversation(request, conv_id):
    form = MessageForm(request.POST or None)
    if request.method == "POST":
        try:
            throttle(request, f"msg:{request.user.pk}", 60, 60)
            if form.is_valid():
                services.send(request.user, conv_id, form.cleaned_data["body"])
                return redirect("messaging:conversation", conv_id)
        except AppError as e:
            if e.code == "not_found":
                raise Http404
            form.add_error(None, e.message)
    conv, other, msgs = or_404(services.open_conversation, request.user, conv_id)
    return render(request, "messaging/conversation.html", {"conv": conv, "other": other, "msgs": msgs, "form": form})


@post_action
def start(request):
    throttle(request, f"msg:start:{request.user.pk}", 30, 3600)
    form = MessageForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Write a message first.")
        return redirect(back(request))
    recipient = User.objects.filter(pk=_uuid(request.POST.get("recipient"))).first()
    if not recipient:
        raise Http404
    listing_id, gig_id = _uuid(request.POST.get("listing")), _uuid(request.POST.get("gig"))
    listing = Listing.objects.filter(pk=listing_id).first() if listing_id else None
    gig = Gig.objects.filter(pk=gig_id).first() if gig_id else None
    conv = services.start_conversation(request.user, recipient=recipient, body=form.cleaned_data["body"], listing=listing, gig=gig)
    return redirect("messaging:conversation", conv.pk)

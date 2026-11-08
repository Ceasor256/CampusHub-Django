"""Private messaging. Users contact each other without exposing phone numbers."""

import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey("marketplace.Listing", null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    gig = models.ForeignKey("gigs.Gig", null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    # Deterministic key so the same pair + subject reuses one thread.
    thread_key = models.CharField(max_length=200, unique=True)
    last_message_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at"]


class Participant(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_memberships")
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conversation", "user"], name="participant_uq")]


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messages_sent")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

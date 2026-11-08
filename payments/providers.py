"""
Payment provider boundary (Phase 2).

Real integrations (MTN MoMo, Airtel Money, or an aggregator such as
Flutterwave / Pesapal / DPO) implement `PaymentProvider` from the provider's
official API documentation. Rules:
  - Secrets stay on the server (environment variables).
  - A payment is "succeeded" only after a verified webhook or a server-side
    status query. Browser redirects prove nothing.
  - Webhooks are idempotent (PaymentEvent unique on provider + event_id).
"""

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Payment, PaymentEvent


@dataclass
class ProviderEvent:
    event_id: str
    provider_ref: str
    status: str  # succeeded | failed | cancelled
    amount_ugx: int
    failure_reason: str = ""


class PaymentProvider:
    name = "base"
    is_test = False

    def initiate(self, *, payment_id, amount_ugx, phone, method, description) -> str:
        raise NotImplementedError

    def verify_webhook(self, raw_body: bytes, headers) -> bool:
        raise NotImplementedError

    def parse_webhook(self, raw_body: bytes) -> ProviderEvent:
        raise NotImplementedError


class TestPaymentProvider(PaymentProvider):
    """Never moves money. Every record it touches is is_test=True and labelled TEST."""

    name = "test"
    is_test = True

    def __init__(self, secret: str):
        self.secret = secret.encode()

    def initiate(self, **_):
        return f"test_{uuid.uuid4()}"

    def sign(self, raw_body: bytes) -> str:
        return hmac.new(self.secret, raw_body, hashlib.sha256).hexdigest()

    def verify_webhook(self, raw_body, headers):
        return hmac.compare_digest(headers.get("X-CampusHub-Signature", ""), self.sign(raw_body))

    def parse_webhook(self, raw_body):
        j = json.loads(raw_body)
        if not isinstance(j.get("eventId"), str) or not isinstance(j.get("providerRef"), str):
            raise ValueError("malformed")
        if j.get("status") not in {"succeeded", "failed", "cancelled"} or not isinstance(j.get("amountUgx"), int):
            raise ValueError("malformed")
        return ProviderEvent(j["eventId"], j["providerRef"], j["status"], j["amountUgx"], j.get("failureReason", ""))


def get_provider(name=None) -> PaymentProvider:
    name = name or settings.PAYMENT_PROVIDER
    if name == "test":
        return TestPaymentProvider(settings.PAYMENT_WEBHOOK_SECRET)
    raise LookupError(f'Payment provider "{name}" is not configured.')


def handle_webhook(provider: PaymentProvider, raw_body: bytes, headers) -> tuple[int, str]:
    """Verify, record and apply a provider webhook exactly once. Amount mismatches are rejected."""
    if not provider.verify_webhook(raw_body, headers):
        return 401, "invalid signature"
    try:
        event = provider.parse_webhook(raw_body)
    except (ValueError, json.JSONDecodeError):
        return 400, "malformed"
    with transaction.atomic():
        try:
            with transaction.atomic():
                record = PaymentEvent.objects.create(provider=provider.name, event_id=event.event_id, payload=json.loads(raw_body))
        except IntegrityError:
            return 200, "duplicate ignored"
        p = Payment.objects.select_for_update().filter(provider=provider.name, provider_ref=event.provider_ref).first()
        if not p:
            return 404, "unknown payment"
        if p.amount_ugx != event.amount_ugx:
            return 422, "amount mismatch"
        if p.status != "pending":
            return 200, "already final"
        p.status, p.failure_reason = event.status, event.failure_reason[:300]
        p.save(update_fields=["status", "failure_reason", "updated_at"])
        record.processed_at = timezone.now()
        record.save(update_fields=["processed_at"])
    return 200, "ok"

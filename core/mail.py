import logging

from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger("campushub.mail")


class OutboxBackend(BaseEmailBackend):
    """
    Development email backend: stores messages in EmailOutbox (viewable at
    /dev/outbox/) and logs them. Nothing leaves the machine.
    Production: set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
    (or a provider backend) via environment variables.
    """

    def send_messages(self, email_messages):
        from core.models import EmailOutbox

        for m in email_messages:
            EmailOutbox.objects.create(to=", ".join(m.to), subject=m.subject, body=m.body)
            log.info("[email] to=%s subject=%r\n%s", m.to, m.subject, m.body)
        return len(email_messages)

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import StaffRole
from core.utils import audit


class Command(BaseCommand):
    help = "Grant the CampusHub admin role to an existing account: manage.py make_admin you@example.com"

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, email, **opts):
        user = get_user_model().objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError(f"No account with email {email}. Register first.")
        StaffRole.objects.get_or_create(user=user, role="admin")
        audit(None, "role.grant.cli", "user", user.pk, {"role": "admin"})
        self.stdout.write(self.style.SUCCESS(f"{user.full_name} <{user.email}> is now an admin."))

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.seed import seed_reference, seed_samples


class Command(BaseCommand):
    help = "Load reference data (campuses, categories) and, unless --reference-only, development sample data."

    def add_arguments(self, parser):
        parser.add_argument("--reference-only", action="store_true", help="Production-safe: no sample users or listings.")

    def handle(self, *args, reference_only=False, **opts):
        seed_reference()
        self.stdout.write(self.style.SUCCESS("Reference data ready (institutions, campuses, categories)."))
        if reference_only:
            return
        if not settings.DEBUG:
            raise CommandError("Refusing to load sample data with DJANGO_DEBUG off. Use --reference-only.")
        created = seed_samples()
        self.stdout.write("Sample data created. Dev logins: core/seed.py (DEV_ACCOUNTS)." if created else "Sample data already present.")

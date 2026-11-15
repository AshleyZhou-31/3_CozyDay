"""Create or update the staff reviewer account used for A10 grading.

The password is read from an environment variable so it is never committed,
printed, or embedded in deployment scripts.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the A10 staff reviewer account."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="mohitg2")

    def handle(self, *args, **options):
        password = os.environ.get("A10_REVIEWER_PASSWORD")
        if not password:
            raise CommandError("Set A10_REVIEWER_PASSWORD before running this command.")

        User = get_user_model()
        user, created = User.objects.get_or_create(username=options["username"])
        user.is_active = True
        user.is_staff = True
        user.is_superuser = False
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} staff reviewer account '{user.username}'.")
        )

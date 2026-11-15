import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class A10ReviewerAccountCommandTests(TestCase):
    def test_password_environment_variable_is_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(CommandError, "A10_REVIEWER_PASSWORD"):
                call_command("setup_a10_reviewer")

    def test_command_creates_staff_reviewer_without_superuser_access(self):
        output = StringIO()
        with patch.dict(os.environ, {"A10_REVIEWER_PASSWORD": "review-password"}):
            call_command("setup_a10_reviewer", stdout=output)

        user = get_user_model().objects.get(username="mohitg2")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("review-password"))
        self.assertIn("Created staff reviewer account", output.getvalue())

    def test_command_updates_existing_account_and_password(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="mohitg2", password="old-password", is_staff=False
        )

        with patch.dict(os.environ, {"A10_REVIEWER_PASSWORD": "new-password"}):
            call_command("setup_a10_reviewer")

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("new-password"))

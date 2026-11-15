import sys
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase

from cozyday.monitoring import SCRUBBED, init_sentry, scrub_event


class InitSentryTests(SimpleTestCase):
    def test_no_dsn_means_off_and_nothing_is_imported(self):
        fake = MagicMock()
        with patch.dict(sys.modules, {"sentry_sdk": fake}):
            self.assertFalse(init_sentry({}))
            self.assertFalse(init_sentry({"SENTRY_DSN": ""}))
            self.assertFalse(init_sentry({"SENTRY_DSN": "   "}))
        fake.init.assert_not_called()

    def test_app_settings_load_without_a_dsn(self):
        self.assertIn("SENTRY_ENABLED", dir(settings))
        self.assertFalse(settings.SENTRY_ENABLED)

    def test_missing_package_is_a_warning_not_a_crash(self):
        with patch.dict(sys.modules, {"sentry_sdk": None}):
            with self.assertLogs("cozyday.monitoring", level="WARNING"):
                self.assertFalse(init_sentry({"SENTRY_DSN": "https://key@example.invalid/1"}))

    def test_dsn_starts_sentry_with_privacy_settings(self):
        fake = MagicMock()
        env = {
            "SENTRY_DSN": "https://key@example.invalid/1",
            "SENTRY_ENVIRONMENT": "staging",
            "SENTRY_TRACES_SAMPLE_RATE": "0.25",
        }
        with patch.dict(sys.modules, {"sentry_sdk": fake}):
            self.assertTrue(init_sentry(env))
        kwargs = fake.init.call_args.kwargs
        self.assertEqual(kwargs["dsn"], env["SENTRY_DSN"])
        self.assertEqual(kwargs["environment"], "staging")
        self.assertEqual(kwargs["traces_sample_rate"], 0.25)
        self.assertIs(kwargs["send_default_pii"], False)
        self.assertIs(kwargs["include_local_variables"], False)
        self.assertEqual(kwargs["max_request_body_size"], "never")
        self.assertIs(kwargs["before_send"], scrub_event)

    def test_bad_sample_rate_falls_back_to_zero(self):
        fake = MagicMock()
        for bad in ("abc", "5", "-1"):
            with patch.dict(sys.modules, {"sentry_sdk": fake}):
                init_sentry({"SENTRY_DSN": "https://key@example.invalid/1",
                             "SENTRY_TRACES_SAMPLE_RATE": bad})
            self.assertEqual(fake.init.call_args.kwargs["traces_sample_rate"], 0.0)

    def test_failure_inside_sentry_init_does_not_break_the_app(self):
        fake = MagicMock()
        fake.init.side_effect = RuntimeError("bad dsn")
        with patch.dict(sys.modules, {"sentry_sdk": fake}):
            self.assertFalse(init_sentry({"SENTRY_DSN": "not-a-dsn"}))


class ScrubEventTests(SimpleTestCase):
    def test_removes_user_text_and_identity(self):
        event = {
            "request": {
                "method": "POST",
                "url": "https://example.test/planitems/ai-rag-planner/?q=my private plan",
                "data": {"query": "my private plan"},
                "cookies": {"sessionid": "secret"},
                "headers": {"Authorization": "Bearer secret"},
                "query_string": "q=my private plan",
            },
            "user": {"id": 5, "email": "someone@example.com"},
            "extra": {"query": "my private plan"},
            "breadcrumbs": {"values": [{"message": "my private plan"}]},
            "exception": {"values": [{"type": "ValueError", "value": "bad: my private plan"}]},
            "logentry": {"message": "failed for my private plan"},
            "message": "my private plan",
        }
        cleaned = scrub_event(event)
        text = repr(cleaned)
        self.assertNotIn("private plan", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("someone@example.com", text)
        self.assertEqual(cleaned["request"]["method"], "POST")
        self.assertTrue(cleaned["request"]["url"].endswith("/planitems/ai-rag-planner/"))
        self.assertEqual(cleaned["exception"]["values"][0]["type"], "ValueError")
        self.assertEqual(cleaned["exception"]["values"][0]["value"], SCRUBBED)

    def test_handles_sparse_events(self):
        self.assertEqual(scrub_event({}), {})
        self.assertEqual(scrub_event({"exception": None}), {"exception": None})

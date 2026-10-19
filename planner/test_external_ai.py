"""Tests for the external Gemini AI feature; no real network calls are made."""

from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .ai_planner import PlannerResult
from .external_ai import (
    ExternalAIConfigurationError,
    ExternalAIResponseError,
    ExternalAITemporaryError,
    generate_external_plan,
)
from .models import PlanItem


GOOD_RESPONSE = (
    "Priority: Finish the report\n"
    "Schedule:\n"
    "1. Draft the report this morning.\n"
    "2. Review it after lunch.\n"
    "Reason: The report is the most urgent task."
)


def gemini_response(text=GOOD_RESPONSE, status=200):
    response = Mock(status_code=status)
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }
    return response


@override_settings(
    GEMINI_API_KEY="test-key-not-a-secret",
    GEMINI_MODEL="gemini-2.5-flash-lite",
    GEMINI_API_TIMEOUT_SECONDS=7,
)
class ExternalAIServiceTests(SimpleTestCase):
    def test_success_uses_header_timeout_and_structured_payload(self):
        post = Mock(return_value=gemini_response())

        result = generate_external_plan(
            "  Plan   my day\n", ["Write report"], request_post=post
        )

        self.assertEqual(result.priority, "Finish the report")
        self.assertEqual(len(result.schedule), 2)
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertIn("gemini-2.5-flash-lite:generateContent", url)
        self.assertNotIn("test-key-not-a-secret", url)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key-not-a-secret")
        self.assertEqual(kwargs["timeout"], 7)
        sent_text = kwargs["json"]["contents"][0]["parts"][0]["text"]
        self.assertEqual(sent_text, "Plan my day My open plan items: Write report.")
        self.assertIn("Use exactly these three headings", kwargs["json"]["systemInstruction"]["parts"][0]["text"])

    @override_settings(GEMINI_API_KEY="")
    def test_missing_key_fails_before_network_request(self):
        post = Mock()
        with self.assertRaises(ExternalAIConfigurationError):
            generate_external_plan("Plan my day", request_post=post)
        post.assert_not_called()

    def test_timeout_is_converted_to_safe_error(self):
        post = Mock(side_effect=requests.Timeout("private transport details"))
        with self.assertRaises(ExternalAITemporaryError) as ctx:
            generate_external_plan("Plan my day", request_post=post)
        self.assertIn("timed out", ctx.exception.user_message)
        self.assertNotIn("private", ctx.exception.user_message)

    def test_connection_failure_is_converted_to_safe_error(self):
        post = Mock(side_effect=requests.ConnectionError("host details"))
        with self.assertRaises(ExternalAITemporaryError):
            generate_external_plan("Plan my day", request_post=post)

    def test_bad_credentials_have_configuration_message(self):
        with self.assertRaises(ExternalAIConfigurationError):
            generate_external_plan(
                "Plan my day", request_post=Mock(return_value=gemini_response(status=403))
            )

    def test_rate_limit_has_temporary_message(self):
        with self.assertRaises(ExternalAITemporaryError) as ctx:
            generate_external_plan(
                "Plan my day", request_post=Mock(return_value=gemini_response(status=429))
            )
        self.assertIn("quota", ctx.exception.user_message)

    def test_invalid_json_is_rejected(self):
        response = gemini_response()
        response.json.side_effect = ValueError("invalid json")
        with self.assertRaises(ExternalAIResponseError):
            generate_external_plan("Plan my day", request_post=Mock(return_value=response))

    def test_safety_block_is_reported_without_raw_provider_data(self):
        response = gemini_response()
        response.json.return_value = {"promptFeedback": {"blockReason": "SAFETY"}}
        with self.assertRaises(ExternalAIResponseError) as ctx:
            generate_external_plan("Plan my day", request_post=Mock(return_value=response))
        self.assertIn("reword", ctx.exception.user_message)

    def test_unstructured_provider_output_is_rejected(self):
        response = gemini_response("Here is a general suggestion.")
        with self.assertRaises(ExternalAIResponseError):
            generate_external_plan("Plan my day", request_post=Mock(return_value=response))


class ExternalAIPlannerViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="ashley", password="pass12345")
        self.other = User.objects.create_user(username="other", password="pass12345")
        PlanItem.objects.create(user=self.user, title="My open item")
        PlanItem.objects.create(user=self.user, title="My completed item", is_completed=True)
        PlanItem.objects.create(user=self.other, title="Other user's private item")
        self.url = reverse("planner:api-ai-planner")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_authenticated_get_shows_disclosure(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "sent to Google")
        self.assertContains(response, "Do not enter sensitive personal information")

    @patch("planner.views.generate_external_plan")
    def test_post_only_includes_current_users_open_titles_when_selected(self, generate):
        generate.return_value = PlannerResult(
            priority="My open item", schedule=["Do it now."], reason="It is open."
        )
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {"request_text": "Plan today", "include_plan_items": "on"},
        )

        self.assertEqual(response.status_code, 200)
        generate.assert_called_once_with("Plan today", ["My open item"])
        self.assertContains(response, "Your API-generated plan")

    @patch("planner.views.generate_external_plan")
    def test_checkbox_off_sends_no_database_titles(self, generate):
        generate.return_value = PlannerResult("A", ["Do A"], "Because")
        self.client.force_login(self.user)
        self.client.post(self.url, {"request_text": "Plan today"})
        generate.assert_called_once_with("Plan today", [])

    @patch("planner.views.generate_external_plan")
    def test_output_is_html_escaped(self, generate):
        generate.return_value = PlannerResult(
            "<script>alert(1)</script>", ["<b>unsafe</b>"], "<img src=x>"
        )
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"request_text": "Plan today"})
        self.assertNotContains(response, "<script>alert(1)</script>", html=False)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;", html=False)

    @patch("planner.views.generate_external_plan")
    def test_safe_service_error_is_rendered(self, generate):
        generate.side_effect = ExternalAITemporaryError("Please try again later.")
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"request_text": "Plan today"})
        self.assertContains(response, "Please try again later")
        self.assertContains(response, 'role="alert"', html=False)

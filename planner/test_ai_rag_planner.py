"""Focused tests for the Django RAG Planner workflow (Stage 2: the view now
calls the real local RAG engine; the mock Stage 1 adapter is gone)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import PlanItem
from .rag_planner import RAGPlannerError


class AIRAGPlannerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="rag_user", password="test-password")
        cls.other = User.objects.create_user(username="other_rag_user", password="test-password")
        PlanItem.objects.create(user=cls.user, title="My private task")
        PlanItem.objects.create(user=cls.other, title="Another user's private task")
        cls.url = reverse("planner:ai-rag-planner")

    def setUp(self):
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_get_shows_form_and_authenticated_navigation_link(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What would you like help planning?")
        self.assertContains(response, f'href="{self.url}"')

    def test_valid_post_displays_complete_response_contract(self):
        response_data = {
            "answer": "Break the paper into smaller steps.",
            "retrieved_chunks": [
                {"id": "TASK-001", "text": "Start by outlining the major sections.", "score": 0.82}
            ],
            "latency_seconds": 0.125,
            "warning": None,
        }
        with patch("planner.views.generate_rag_plan", return_value=response_data) as generate:
            response = self.client.post(self.url, {"query": "  How do I break up a paper?  "})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How do I break up a paper?")
        self.assertContains(response, "Break the paper into smaller steps.")
        self.assertContains(response, "TASK-001")
        self.assertContains(response, "Start by outlining the major sections.")
        self.assertContains(response, "0.125 seconds")
        generate.assert_called_once_with("How do I break up a paper?", user=self.user)

    def test_real_adapter_delegates_to_rag_engine(self):
        """Stage 2: the mock adapter is gone; generate_rag_plan now calls the
        local RAG engine directly (still mocked here so no model is loaded)."""
        fake_result = {
            "answer": "Break the paper into milestones: topic, outline, draft, revise, submit.",
            "retrieved_chunks": [{"id": "HYBRID_002", "text": "Split into milestones.", "score": 0.91}],
            "latency_seconds": 0.42,
            "warning": None,
        }
        with patch("planner.rag_engine.answer_query", return_value=fake_result):
            response = self.client.post(self.url, {"query": "How should I plan a study week?"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Break the paper into milestones")
        self.assertNotContains(response, "Stage 1 mock response only")
        self.assertNotContains(response, "STAGE1-MOCK")

    def test_empty_and_whitespace_only_input_do_not_call_service(self):
        with patch("planner.views.generate_rag_plan") as generate:
            empty = self.client.post(self.url, {"query": ""})
            whitespace = self.client.post(self.url, {"query": "   \n\t "})

        self.assertEqual(empty.status_code, 200)
        self.assertContains(empty, "This field is required.")
        self.assertEqual(whitespace.status_code, 200)
        self.assertContains(whitespace, "This field is required.")
        generate.assert_not_called()

    @override_settings(AI_PLANNER_MAX_INPUT_CHARS=30)
    def test_excessively_long_input_is_rejected(self):
        with patch("planner.views.generate_rag_plan") as generate:
            response = self.client.post(self.url, {"query": "x" * 31})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "under 30")
        generate.assert_not_called()

    def test_service_failure_returns_safe_message_without_server_error(self):
        failure = RAGPlannerError("The local assistant is unavailable.")
        with patch("planner.views.generate_rag_plan", side_effect=failure):
            response = self.client.post(self.url, {"query": "Plan my study week"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The local assistant is unavailable.")

    def test_unexpected_failure_and_malformed_result_are_handled_safely(self):
        for output in [RuntimeError("private query must not be logged"), {"answer": None}]:
            with self.subTest(output=type(output).__name__):
                kwargs = (
                    {"side_effect": output}
                    if isinstance(output, Exception)
                    else {"return_value": output}
                )
                with patch("planner.views.generate_rag_plan", **kwargs):
                    response = self.client.post(self.url, {"query": "Plan my study week"})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "temporarily unavailable")
                self.assertNotContains(response, "private query must not be logged")

    def test_untrusted_question_and_source_text_are_html_escaped(self):
        result = {
            "answer": "<script>alert(1)</script>",
            "retrieved_chunks": [{"id": "<b>src</b>", "text": "<img src=x>", "score": 0.2}],
            "latency_seconds": 0.01,
            "warning": None,
        }
        with patch("planner.views.generate_rag_plan", return_value=result):
            response = self.client.post(self.url, {"query": "<script>question</script>"})

        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;question&lt;/script&gt;")
        self.assertContains(response, "&lt;img src=x&gt;")

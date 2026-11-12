from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import AIPerformanceEvent


class A10PerformanceLoggingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="lin-test", password="test-password-123"
        )
        self.client.force_login(self.user)

    @patch("planner.views.generate_rag_plan")
    def test_successful_request_records_stage_timings_without_prompt(self, generate):
        generate.return_value = {
            "answer": "Break the task into steps.",
            "structured_plan": {
                "goal": "Break the task into steps.", "time_period": "Not specified",
                "priorities": [], "tasks_or_phases": ["Break into steps"],
                "deadlines": [], "recommended_next_steps": ["Choose a first step"],
            },
            "template_type": "general",
            "outcome": "success",
            "retrieved_chunks": [{"id": "CHUNK_1", "text": "guidance", "score": .72}],
            "latency_seconds": .12,
            "stage_latencies": {"embedding": .02, "retrieval": .01, "generation": .07},
            "warning": None,
        }

        response = self.client.post(
            reverse("planner:ai-rag-planner"),
            {"query": "PRIVATE PROMPT CONTENT should not be stored"},
        )

        self.assertEqual(response.status_code, 200)
        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.outcome, AIPerformanceEvent.Outcome.SUCCESS)
        self.assertEqual(event.embedding_latency_ms, 20)
        self.assertEqual(event.retrieval_latency_ms, 10)
        self.assertEqual(event.generation_latency_ms, 70)
        self.assertEqual(event.max_similarity_score, .72)
        self.assertEqual(event.retrieved_count, 1)
        self.assertIsNone(event.query_length_chars)
        self.assertIsNone(event.query_category)
        self.assertIsNone(event.input_tokens_estimate)
        self.assertIsNone(event.output_tokens_estimate)
        self.assertIsNone(event.estimated_cost_usd)
        self.assertFalse(event.is_simulated)
        self.assertEqual(event.template_type, "general")
        self.assertNotIn("PRIVATE PROMPT CONTENT", repr(event.__dict__))
        field_names = {field.name for field in AIPerformanceEvent._meta.fields}
        self.assertNotIn("query", field_names)
        self.assertNotIn("user", field_names)
        self.assertNotIn("answer", field_names)

    @patch("planner.views.time.perf_counter", side_effect=[0.0, 10.0, 10.1, 10.2, 15.0])
    @patch("planner.views.generate_rag_plan")
    def test_validation_timer_starts_after_rag_generation(self, generate, _clock):
        generate.side_effect = lambda *args, **kwargs: (
            __import__("planner.views", fromlist=["time"]).time.perf_counter(),
            {
                "answer": "Break the task into steps.",
                "structured_plan": {
                    "goal": "Break the task into steps.", "time_period": "Not specified",
                    "priorities": [], "tasks_or_phases": ["Break into steps"],
                    "deadlines": [], "recommended_next_steps": ["Choose a first step"],
                },
                "template_type": "general",
                "retrieved_chunks": [],
                "latency_seconds": .12,
                "stage_latencies": {"embedding": .02, "retrieval": .01, "generation": .07},
                "warning": None,
            },
        )[1]

        self.client.post(reverse("planner:ai-rag-planner"), {"query": "A valid question"})

        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.validation_latency_ms, 100)
        self.assertEqual(event.total_latency_ms, 15000)

    @patch("planner.views.generate_rag_plan")
    def test_relevance_abstention_is_logged_separately(self, generate):
        generate.return_value = {
            "answer": "I cannot answer that from the guidance.",
            "structured_plan": None,
            "template_type": "general",
            "outcome": "abstention",
            "retrieved_chunks": [{"id": "CHUNK_2", "text": "guidance", "score": .2}],
            "latency_seconds": .03,
            "stage_latencies": {"embedding": .01, "retrieval": .01, "generation": 0},
            "warning": "No closely matching guidance was found.",
        }
        self.client.post(reverse("planner:ai-rag-planner"), {"query": "A valid question"})
        self.assertEqual(AIPerformanceEvent.objects.get().outcome, "abstention")

    @patch("planner.views.generate_rag_plan", side_effect=RuntimeError("internal failure"))
    def test_service_failure_is_logged_without_exception_details(self, _generate):
        response = self.client.post(reverse("planner:ai-rag-planner"), {"query": "A valid question"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AIPerformanceEvent.objects.get().outcome, "error")

    def test_invalid_submission_is_counted_as_error_without_storing_input(self):
        self.client.post(reverse("planner:ai-rag-planner"), {"query": ""})
        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.outcome, "error")
        self.assertEqual(event.retrieved_count, 0)


class A10SystemDashboardAccessTests(TestCase):
    def setUp(self):
        self.url = reverse("planner:system-analytics")

    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/login/?next={self.url}")

    def test_authenticated_non_staff_user_is_forbidden(self):
        user = get_user_model().objects.create_user(username="member", password="test-password-123")
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_staff_dashboard_reports_latency_percentiles_and_outcomes(self):
        staff = get_user_model().objects.create_user(
            username="staff", password="test-password-123", is_staff=True
        )
        self.client.force_login(staff)
        for latency, outcome in ((100, "success"), (200, "abstention"), (1000, "error")):
            AIPerformanceEvent.objects.create(
                outcome=outcome,
                total_latency_ms=latency,
                embedding_latency_ms=10,
                retrieval_latency_ms=20,
                generation_latency_ms=0 if outcome == "abstention" else 50,
            )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["event_count"], 3)
        self.assertEqual(response.context["mean_latency"], 433)
        self.assertEqual(response.context["median_latency"], 200)
        self.assertEqual(response.context["p95_latency"], 920)
        self.assertEqual(response.context["success_rate"], 33.3)
        self.assertEqual(response.context["abstention_rate"], 33.3)
        self.assertEqual(response.context["error_rate"], 33.3)
        self.assertContains(response, "Average stage time")
        self.assertContains(response, "Request outcomes")
        self.assertContains(response, "Success rate")
        self.assertContains(response, "33.3%")

    def test_empty_dashboard_has_a_clear_state(self):
        staff = get_user_model().objects.create_user(
            username="staff-empty", password="test-password-123", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No RAG Planner requests have been recorded yet.")

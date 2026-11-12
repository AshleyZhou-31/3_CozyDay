from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import AIPerformanceEvent
from .views import categorize_query


class CategorizeQueryUnitTests(TestCase):
    """Direct unit tests on the categorization function -- no request cycle needed."""

    def test_returns_none_for_empty_or_whitespace_input(self):
        self.assertIsNone(categorize_query(""))
        self.assertIsNone(categorize_query("   "))
        self.assertIsNone(categorize_query(None))

    def test_returns_other_for_unmatched_query(self):
        self.assertEqual(
            categorize_query("What is the capital of France?"),
            AIPerformanceEvent.QueryCategory.OTHER,
        )
        self.assertEqual(categorize_query("help"), AIPerformanceEvent.QueryCategory.OTHER)

    def test_matches_each_documented_category(self):
        cases = [
            ("How should I break this big paper down into smaller tasks?",
             AIPerformanceEvent.QueryCategory.TASK_BREAKDOWN),
            ("These three things all feel urgent, what should I do first?",
             AIPerformanceEvent.QueryCategory.PRIORITIZATION),
            ("How do I build a weekly study plan for my exam?",
             AIPerformanceEvent.QueryCategory.STUDY_PLANNING),
            ("I want to share this plan with a teammate without exposing private notes.",
             AIPerformanceEvent.QueryCategory.PRIVACY_SHARING),
            ("How do I turn my completion analytics into a progress report?",
             AIPerformanceEvent.QueryCategory.PROGRESS_REPORTING),
        ]
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(categorize_query(query), expected)

    def test_is_case_insensitive(self):
        self.assertEqual(
            categorize_query("STUDY for my EXAM"),
            AIPerformanceEvent.QueryCategory.STUDY_PLANNING,
        )

    def test_precedence_order_is_deterministic_on_overlap(self):
        # Contains both a task_breakdown keyword ("steps") and a
        # study_planning keyword ("exam"). task_breakdown is checked first
        # in the documented precedence order, so it must win.
        query = "Help me break down my exam prep into steps."
        self.assertEqual(categorize_query(query), AIPerformanceEvent.QueryCategory.TASK_BREAKDOWN)


class UserBehaviorLoggingTests(TestCase):
    """Integration tests through the real view, covering Ashley's required behavior."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rishabh-test", password="test-password-123"
        )
        self.client.force_login(self.user)

    @patch("planner.views.generate_rag_plan")
    def test_successful_query_populates_length_and_category(self, generate):
        generate.return_value = {
            "answer": "Break it into steps.",
            "outcome": "success",
            "retrieved_chunks": [{"id": "CHUNK_1", "text": "guidance", "score": .8}],
            "latency_seconds": .1,
            "stage_latencies": {"embedding": .01, "retrieval": .01, "generation": .05},
            "warning": None,
        }
        query = "How should I break this project down into smaller tasks?"

        self.client.post(reverse("planner:ai-rag-planner"), {"query": query})

        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.query_length_chars, len(query))
        self.assertEqual(event.query_category, AIPerformanceEvent.QueryCategory.TASK_BREAKDOWN)

    @patch("planner.views.generate_rag_plan")
    def test_unmatched_query_is_categorized_as_other(self, generate):
        generate.return_value = {
            "answer": "I cannot answer that from the guidance.",
            "outcome": "abstention",
            "retrieved_chunks": [],
            "latency_seconds": .02,
            "stage_latencies": {"embedding": .01, "retrieval": .01, "generation": 0},
            "warning": "No closely matching guidance was found.",
        }

        self.client.post(reverse("planner:ai-rag-planner"), {"query": "What is the capital of France?"})

        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.query_category, AIPerformanceEvent.QueryCategory.OTHER)

    def test_invalid_form_submission_leaves_length_and_category_empty(self):
        self.client.post(reverse("planner:ai-rag-planner"), {"query": ""})

        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.outcome, "error")
        self.assertIsNone(event.query_length_chars)
        self.assertIsNone(event.query_category)

    @patch("planner.views.generate_rag_plan", side_effect=RuntimeError("internal failure"))
    def test_service_failure_after_valid_form_still_categorizes_query(self, _generate):
        # The form itself passed Django validation (the query was clean)
        # even though the RAG service raised afterward -- query should
        # still be categorized, since form.cleaned_data["query"] was
        # available at that call site.
        self.client.post(
            reverse("planner:ai-rag-planner"),
            {"query": "How do I build a weekly study plan for my exam?"},
        )

        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.outcome, "error")
        self.assertEqual(event.query_category, AIPerformanceEvent.QueryCategory.STUDY_PLANNING)

    @patch("planner.views.generate_rag_plan")
    def test_no_raw_query_text_is_ever_persisted(self, generate):
        generate.return_value = {
            "answer": "Break it into steps.",
            "outcome": "success",
            "retrieved_chunks": [],
            "latency_seconds": .1,
            "stage_latencies": {"embedding": .01, "retrieval": .01, "generation": .05},
            "warning": None,
        }
        distinctive_query = "SECRET_MARKER_text_that_must_never_be_stored_anywhere"

        self.client.post(reverse("planner:ai-rag-planner"), {"query": distinctive_query})

        event = AIPerformanceEvent.objects.get()
        field_names = {field.name for field in AIPerformanceEvent._meta.fields}
        self.assertNotIn("query", field_names)
        # Stricter than a field-name check: confirm no stored field's value
        # contains the raw query text as a substring, not just that no field
        # happens to be named "query".
        for field in AIPerformanceEvent._meta.fields:
            value = getattr(event, field.name)
            if isinstance(value, str):
                self.assertNotIn(distinctive_query, value)

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
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
            "structured_plan": {
                "goal": "Break it into steps.", "time_period": "Not specified",
                "priorities": [], "tasks_or_phases": ["Break into steps"],
                "deadlines": [], "recommended_next_steps": ["Choose a first step"],
            },
            "template_type": "general",
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
            "structured_plan": None,
            "template_type": "general",
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
            "structured_plan": {
                "goal": "Break it into steps.", "time_period": "Not specified",
                "priorities": [], "tasks_or_phases": ["Break into steps"],
                "deadlines": [], "recommended_next_steps": ["Choose a first step"],
            },
            "template_type": "general",
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


class A10Stage2DashboardWidgetTests(TestCase):
    """Dashboard widget tests for Stage 2: daily request volume, category
    breakdown (including the uncategorized bucket), the topic/outcome
    table, and the 14-day versus 30-day reporting windows."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff-widgets", password="test-password-123", is_staff=True
        )
        self.client.force_login(self.staff)
        self.url = reverse("planner:system-analytics")

    def _create_event(self, *, days_ago=0, category=None, length=None, outcome="success"):
        event = AIPerformanceEvent.objects.create(
            outcome=outcome,
            total_latency_ms=100,
            query_category=category,
            query_length_chars=length,
        )
        if days_ago:
            backdated = timezone.now() - timedelta(days=days_ago)
            AIPerformanceEvent.objects.filter(pk=event.pk).update(created_at=backdated)
        return event

    def test_daily_request_volume_counts_only_last_14_days(self):
        self._create_event(days_ago=0)
        self._create_event(days_ago=0)
        self._create_event(days_ago=13)
        self._create_event(days_ago=20)  # outside the 14-day trend window

        response = self.client.get(self.url)
        daily = response.context["daily"]
        self.assertEqual(len(daily), 14)
        self.assertEqual(daily[-1]["count"], 2)  # today
        self.assertEqual(daily[0]["count"], 1)  # 13 days ago, oldest row in window
        self.assertEqual(sum(row["count"] for row in daily), 3)  # 20-day-old event excluded

    def test_category_counts_and_uncategorized_bucket(self):
        self._create_event(category=AIPerformanceEvent.QueryCategory.TASK_BREAKDOWN)
        self._create_event(category=AIPerformanceEvent.QueryCategory.TASK_BREAKDOWN)
        self._create_event(category=AIPerformanceEvent.QueryCategory.STUDY_PLANNING)
        self._create_event(category=None)

        response = self.client.get(self.url)
        category_rows = {row["key"]: row for row in response.context["category_rows"]}
        self.assertEqual(category_rows["task_breakdown"]["count"], 2)
        self.assertEqual(category_rows["study_planning"]["count"], 1)
        self.assertEqual(category_rows["prioritization"]["count"], 0)
        self.assertEqual(category_rows["uncategorized"]["count"], 1)

    def test_topic_outcome_table_tracks_average_length_and_outcome_split(self):
        self._create_event(
            category=AIPerformanceEvent.QueryCategory.PRIORITIZATION, length=40, outcome="success"
        )
        self._create_event(
            category=AIPerformanceEvent.QueryCategory.PRIORITIZATION, length=60, outcome="error"
        )

        response = self.client.get(self.url)
        comparison_rows = {row["label"]: row for row in response.context["comparison_rows"]}
        row = comparison_rows["Prioritization"]
        self.assertEqual(row["count"], 2)
        self.assertEqual(row["avg_length"], 50)
        self.assertEqual(row["success"], 1)
        self.assertEqual(row["error"], 1)
        self.assertEqual(row["abstention"], 0)

    def test_category_with_no_events_shows_zero_count_and_no_average(self):
        response = self.client.get(self.url)
        comparison_rows = {row["label"]: row for row in response.context["comparison_rows"]}
        row = comparison_rows["Progress reporting"]
        self.assertEqual(row["count"], 0)
        self.assertIsNone(row["avg_length"])

    def test_events_older_than_30_days_are_excluded_entirely(self):
        self._create_event(days_ago=35, category=AIPerformanceEvent.QueryCategory.OTHER)

        response = self.client.get(self.url)
        category_rows = {row["key"]: row for row in response.context["category_rows"]}
        self.assertEqual(category_rows["other"]["count"], 0)
        self.assertEqual(response.context["event_count"], 0)

    def test_event_between_14_and_30_days_counts_for_category_but_not_daily_trend(self):
        self._create_event(days_ago=20, category=AIPerformanceEvent.QueryCategory.STUDY_PLANNING)

        response = self.client.get(self.url)
        category_rows = {row["key"]: row for row in response.context["category_rows"]}
        self.assertEqual(category_rows["study_planning"]["count"], 1)
        daily_total = sum(row["count"] for row in response.context["daily"])
        self.assertEqual(daily_total, 0)

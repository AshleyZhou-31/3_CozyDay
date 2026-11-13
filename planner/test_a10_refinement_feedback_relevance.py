from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from planner.models import AIPerformanceEvent, AIResponseFeedback


SUCCESS_RESULT = {
    "answer": "Break it into steps.",
    "structured_plan": {
        "goal": "Break it into steps.", "time_period": "Not specified",
        "priorities": [], "tasks_or_phases": ["Break into steps"],
        "deadlines": [], "recommended_next_steps": ["Choose a first step"],
    },
    "template_type": "general",
    "outcome": "success",
    "retrieved_chunks": [
        {"id": "CHUNK_1", "text": "guidance", "score": .64},
        {"id": "CHUNK_2", "text": "more guidance", "score": .81},
    ],
    "latency_seconds": .1,
    "stage_latencies": {"embedding": .01, "retrieval": .01, "generation": .05},
    "warning": None,
}


class RelevanceScoreDisplayTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="relevance-test", password="test-password-123"
        )
        self.client.force_login(self.user)

    @patch("planner.views.generate_rag_plan")
    def test_successful_response_includes_best_relevance_score_and_percent(self, generate):
        generate.return_value = dict(SUCCESS_RESULT)

        response = self.client.post(
            reverse("planner:ai-rag-planner"), {"query": "How should I break this down?"}
        )

        self.assertEqual(response.context["result"]["best_relevance_score"], .81)
        self.assertEqual(response.context["result"]["best_relevance_percent"], 81.0)
        self.assertContains(response, "81.0%")

    @patch("planner.views.generate_rag_plan")
    def test_event_id_is_included_for_the_feedback_form(self, generate):
        generate.return_value = dict(SUCCESS_RESULT)

        self.client.post(reverse("planner:ai-rag-planner"), {"query": "A valid question"})

        response = self.client.post(reverse("planner:ai-rag-planner"), {"query": "Another one"})
        new_event_id = response.context["result"]["event_id"]
        self.assertIsNotNone(new_event_id)
        self.assertTrue(AIPerformanceEvent.objects.filter(pk=new_event_id).exists())

    @patch("planner.views.generate_rag_plan")
    def test_no_retrieved_chunks_leaves_relevance_score_none(self, generate):
        result = dict(SUCCESS_RESULT)
        result["retrieved_chunks"] = []
        generate.return_value = result

        response = self.client.post(reverse("planner:ai-rag-planner"), {"query": "A valid question"})

        self.assertIsNone(response.context["result"]["best_relevance_score"])
        self.assertIsNone(response.context["result"]["best_relevance_percent"])


class FeedbackSubmissionTests(TestCase):
    def setUp(self):
        self.event = AIPerformanceEvent.objects.create(outcome="success", total_latency_ms=100)
        self.url = reverse("planner:ai-rag-planner-feedback", args=[self.event.pk])

    def test_anonymous_submission_redirects_to_login(self):
        response = self.client.post(self.url, {"rating": "accurate"})
        self.assertRedirects(response, f"/login/?next={self.url}")
        self.assertFalse(AIResponseFeedback.objects.exists())

    def test_get_request_is_not_allowed(self):
        user = get_user_model().objects.create_user(username="fb-get", password="test-password-123")
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_valid_rating_creates_feedback_record(self):
        user = get_user_model().objects.create_user(username="fb-valid", password="test-password-123")
        self.client.force_login(user)

        response = self.client.post(self.url, {"rating": "accurate"}, follow=True)

        self.assertRedirects(response, reverse("planner:ai-rag-planner"))
        feedback = AIResponseFeedback.objects.get(event=self.event)
        self.assertEqual(feedback.rating, AIResponseFeedback.Rating.ACCURATE)

    def test_resubmitting_feedback_updates_rather_than_duplicates(self):
        user = get_user_model().objects.create_user(username="fb-resubmit", password="test-password-123")
        self.client.force_login(user)

        self.client.post(self.url, {"rating": "accurate"})
        self.client.post(self.url, {"rating": "not_accurate"})

        self.assertEqual(AIResponseFeedback.objects.filter(event=self.event).count(), 1)
        feedback = AIResponseFeedback.objects.get(event=self.event)
        self.assertEqual(feedback.rating, AIResponseFeedback.Rating.NOT_ACCURATE)

    def test_invalid_rating_value_is_rejected_without_creating_a_record(self):
        user = get_user_model().objects.create_user(username="fb-invalid", password="test-password-123")
        self.client.force_login(user)

        self.client.post(self.url, {"rating": "definitely_maybe"})

        self.assertFalse(AIResponseFeedback.objects.filter(event=self.event).exists())

    def test_unknown_event_id_returns_404(self):
        user = get_user_model().objects.create_user(username="fb-404", password="test-password-123")
        self.client.force_login(user)

        bad_url = reverse("planner:ai-rag-planner-feedback", args=[999999])
        response = self.client.post(bad_url, {"rating": "accurate"})

        self.assertEqual(response.status_code, 404)


class DashboardRefinementWidgetTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff-refinement", password="test-password-123", is_staff=True
        )
        self.client.force_login(self.staff)
        self.url = reverse("planner:system-analytics")

    def _event(self, *, length=None, template_type=None, outcome="success", rating=None):
        event = AIPerformanceEvent.objects.create(
            outcome=outcome, total_latency_ms=100,
            query_length_chars=length, template_type=template_type,
        )
        if rating:
            AIResponseFeedback.objects.create(event=event, rating=rating)
        return event

    def test_query_length_distribution_buckets_correctly(self):
        self._event(length=10)
        self._event(length=35)
        self._event(length=150)
        self._event(length=None)

        response = self.client.get(self.url)
        rows = {row["key"]: row for row in response.context["length_rows"]}
        self.assertEqual(rows["very_short"]["count"], 1)
        self.assertEqual(rows["short"]["count"], 1)
        self.assertEqual(rows["long"]["count"], 1)
        self.assertEqual(rows["unknown"]["count"], 1)
        self.assertEqual(rows["medium"]["count"], 0)

    def test_feedback_distribution_and_accuracy_rate(self):
        self._event(rating=AIResponseFeedback.Rating.ACCURATE)
        self._event(rating=AIResponseFeedback.Rating.ACCURATE)
        self._event(rating=AIResponseFeedback.Rating.NOT_ACCURATE)
        self._event()  # unrated

        response = self.client.get(self.url)
        self.assertEqual(response.context["total_feedback"], 3)
        self.assertEqual(response.context["accuracy_rate"], round(2 / 3 * 100, 1))
        rows = {row["key"]: row for row in response.context["feedback_rows"]}
        self.assertEqual(rows["accurate"]["count"], 2)
        self.assertEqual(rows["not_accurate"]["count"], 1)
        self.assertEqual(rows["partially_accurate"]["count"], 0)

    def test_accuracy_rate_is_none_when_no_feedback_submitted(self):
        self._event()
        self._event()

        response = self.client.get(self.url)
        self.assertIsNone(response.context["accuracy_rate"])
        self.assertEqual(response.context["total_feedback"], 0)

    def test_template_performance_comparison_counts_and_latency(self):
        self._event(template_type="weekly", outcome="success")
        self._event(template_type="weekly", outcome="error")
        self._event(template_type=None, outcome="success")

        response = self.client.get(self.url)
        rows = {row["label"]: row for row in response.context["template_rows"]}
        self.assertEqual(rows["Weekly plan"]["count"], 2)
        self.assertEqual(rows["Weekly plan"]["success"], 1)
        self.assertEqual(rows["Weekly plan"]["error"], 1)
        self.assertEqual(rows["Unknown"]["count"], 1)

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .cost_dashboard import build_cost_context, format_usd
from .models import AIPerformanceEvent

SUCCESS = AIPerformanceEvent.Outcome.SUCCESS
ABSTENTION = AIPerformanceEvent.Outcome.ABSTENTION
CATEGORY = AIPerformanceEvent.QueryCategory


def make_event(**overrides):
    values = dict(
        outcome=SUCCESS,
        total_latency_ms=5000,
        generation_latency_ms=4000,
        query_category=CATEGORY.TASK_BREAKDOWN,
        input_tokens_estimate=400,
        output_tokens_estimate=200,
        estimated_cost_usd=Decimal("0.00016000"),
        model_name="Qwen/Qwen2.5-3B-Instruct",
        serving_backend="transformers-local",
        is_simulated=False,
    )
    values.update(overrides)
    return AIPerformanceEvent.objects.create(**values)


class CostContextTests(TestCase):
    def test_totals_means_and_tokens(self):
        make_event()
        make_event(estimated_cost_usd=Decimal("0.00032000"), output_tokens_estimate=400)
        make_event(outcome=ABSTENTION, generation_latency_ms=0, input_tokens_estimate=0,
                   output_tokens_estimate=0, estimated_cost_usd=Decimal("0"))
        ctx = build_cost_context(list(AIPerformanceEvent.objects.all()))
        self.assertTrue(ctx["cost_has_data"])
        self.assertEqual(ctx["total_cost_text"], "$0.000480")
        self.assertEqual(ctx["mean_cost_text"], "$0.000160")
        self.assertEqual(ctx["input_tokens"], 800)
        self.assertEqual(ctx["output_tokens"], 600)
        self.assertEqual(ctx["total_tokens"], 1400)
        # Abstentions are excluded from generation time.
        self.assertEqual(ctx["mean_generation_ms"], 4000)

    def test_events_without_cost_are_ignored(self):
        make_event(estimated_cost_usd=None, input_tokens_estimate=None, output_tokens_estimate=None)
        ctx = build_cost_context(list(AIPerformanceEvent.objects.all()))
        self.assertFalse(ctx["cost_has_data"])
        self.assertEqual(ctx["total_cost_text"], "—")
        self.assertEqual(ctx["mean_cost_text"], "—")

    def test_empty_input_does_not_divide_by_zero(self):
        ctx = build_cost_context([])
        self.assertFalse(ctx["cost_has_data"])
        self.assertIsNone(ctx["mean_generation_ms"])
        self.assertEqual(ctx["backend_rows"], [])
        self.assertTrue(all(row["cost_width"] == 0 for row in ctx["cost_category_rows"]))

    def test_cost_by_category_and_relative_bar_widths(self):
        make_event(query_category=CATEGORY.TASK_BREAKDOWN, estimated_cost_usd=Decimal("0.0004"))
        make_event(query_category=CATEGORY.PRIORITIZATION, estimated_cost_usd=Decimal("0.0002"))
        make_event(query_category=None, estimated_cost_usd=Decimal("0.0001"))
        rows = {r["label"]: r for r in build_cost_context(list(AIPerformanceEvent.objects.all()))["cost_category_rows"]}
        self.assertEqual(rows["Task breakdown"]["cost_width"], 100)
        self.assertEqual(rows["Prioritization"]["cost_width"], 50)
        self.assertEqual(rows["Uncategorized"]["count"], 1)
        self.assertEqual(rows["Study planning"]["count"], 0)

    def test_backend_comparison_groups_by_backend_and_model(self):
        make_event(serving_backend="transformers-local", total_latency_ms=4000)
        make_event(serving_backend="transformers-local", total_latency_ms=6000)
        make_event(serving_backend="ollama", model_name="qwen2.5:3b", total_latency_ms=2000)
        make_event(serving_backend="", model_name="")
        rows = {r["backend"]: r for r in build_cost_context(list(AIPerformanceEvent.objects.all()))["backend_rows"]}
        self.assertEqual(rows["transformers-local"]["count"], 2)
        self.assertEqual(rows["transformers-local"]["mean_latency_ms"], 5000)
        self.assertEqual(rows["ollama"]["model"], "qwen2.5:3b")
        self.assertEqual(rows["Not recorded"]["count"], 1)

    def test_format_usd(self):
        self.assertEqual(format_usd(Decimal("0.00015600")), "$0.000156")
        self.assertEqual(format_usd(None), "—")


class DashboardPageTests(TestCase):
    def setUp(self):
        self.url = reverse("planner:system-analytics")
        self.staff = get_user_model().objects.create_user(
            username="cost-staff", password="test-password-123", is_staff=True
        )
        self.client.force_login(self.staff)

    def test_page_shows_cost_widgets_labelled_as_estimates(self):
        make_event()
        html = self.client.get(self.url).content.decode()
        for text in ("Total estimated cost", "Mean cost per request", "Total tokens",
                     "Estimated cost by topic", "Token usage by topic",
                     "Cost vs. generation time by topic", "Serving backend comparison"):
            self.assertIn(text, html)
        self.assertIn("Estimated, not billed", html)
        self.assertIn("$0.000160", html)

    def test_empty_database_renders_without_errors(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("No cost data has been recorded yet", response.content.decode())

    def test_simulated_records_are_labelled_and_can_be_hidden(self):
        make_event(is_simulated=False)
        make_event(is_simulated=True, estimated_cost_usd=Decimal("0.0009"))
        html = self.client.get(self.url).content.decode()
        self.assertIn("Includes 1 simulated record", html)
        self.assertIn("Show real requests only", html)
        self.assertIn("$0.001060", html)
        hidden = self.client.get(self.url, {"simulated": "0"}).content.decode()
        self.assertIn("1 simulated record hidden", hidden)
        self.assertIn("$0.000160", hidden)
        self.assertNotIn("$0.001060", hidden)

    def test_non_staff_still_forbidden(self):
        self.client.logout()
        user = get_user_model().objects.create_user(username="plain", password="test-password-123")
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from .models import AIPerformanceEvent

Outcome = AIPerformanceEvent.Outcome


def run(*args):
    out = StringIO()
    call_command("seed_ai_analytics", *args, stdout=out)
    return out.getvalue()


def real_event(**overrides):
    values = dict(outcome=Outcome.SUCCESS, total_latency_ms=4000, is_simulated=False)
    values.update(overrides)
    return AIPerformanceEvent.objects.create(**values)


class SeedCommandTests(TestCase):
    def test_creates_about_100_labelled_simulated_records(self):
        run()
        self.assertEqual(AIPerformanceEvent.objects.count(), 100)
        self.assertEqual(AIPerformanceEvent.objects.filter(is_simulated=True).count(), 100)

    def test_running_twice_does_not_duplicate(self):
        run()
        run()
        run("--count", "100")
        self.assertEqual(AIPerformanceEvent.objects.filter(is_simulated=True).count(), 100)

    def test_real_records_are_never_touched(self):
        keep = real_event()
        legacy = real_event(is_simulated=None)
        run()
        run("--clear")
        self.assertEqual(AIPerformanceEvent.objects.count(), 2)
        self.assertTrue(AIPerformanceEvent.objects.filter(pk=keep.pk).exists())
        self.assertTrue(AIPerformanceEvent.objects.filter(pk=legacy.pk).exists())

    def test_clear_removes_only_simulated_records(self):
        real_event()
        run()
        output = run("--clear")
        self.assertIn("Removed 100", output)
        self.assertEqual(AIPerformanceEvent.objects.filter(is_simulated=True).count(), 0)
        self.assertEqual(AIPerformanceEvent.objects.count(), 1)

    def test_count_option_and_limits(self):
        run("--count", "25")
        self.assertEqual(AIPerformanceEvent.objects.count(), 25)
        for bad in ("0", "501", "-3"):
            with self.assertRaises(CommandError):
                run("--count", bad)

    def test_same_seed_gives_same_values(self):
        run("--seed", "7", "--count", "30")
        first = sorted(AIPerformanceEvent.objects.values_list(
            "outcome", "total_latency_ms", "query_category", "estimated_cost_usd"
        ), key=repr)
        run("--seed", "7", "--count", "30")
        second = sorted(AIPerformanceEvent.objects.values_list(
            "outcome", "total_latency_ms", "query_category", "estimated_cost_usd"
        ), key=repr)
        self.assertEqual(first, second)

    def test_records_are_spread_over_the_last_14_days(self):
        run()
        now = timezone.now()
        times = list(AIPerformanceEvent.objects.values_list("created_at", flat=True))
        self.assertTrue(all(0 <= (now - t).total_seconds() <= 14 * 86400 + 5 for t in times))
        self.assertGreater(len({t.date() for t in times}), 7)

    def test_values_stay_inside_the_verified_a9_ranges(self):
        run()
        for event in AIPerformanceEvent.objects.all():
            self.assertEqual(event.serving_backend, "transformers-local")
            self.assertTrue(event.model_name)
            if event.outcome == Outcome.SUCCESS:
                self.assertTrue(3000 <= event.generation_latency_ms <= 21000)
                self.assertTrue(0.527 <= event.max_similarity_score <= 0.762)
                self.assertGreater(event.estimated_cost_usd, Decimal("0"))
            elif event.outcome == Outcome.ABSTENTION:
                self.assertEqual(event.generation_latency_ms, 0)
                self.assertLess(event.max_similarity_score, 0.35)
                self.assertEqual(event.estimated_cost_usd, Decimal("0"))
            else:
                self.assertIsNone(event.estimated_cost_usd)
                self.assertIsNone(event.query_category)

    def test_mix_includes_all_three_outcomes(self):
        run()
        outcomes = set(AIPerformanceEvent.objects.values_list("outcome", flat=True))
        self.assertEqual(outcomes, {Outcome.SUCCESS, Outcome.ABSTENTION, Outcome.ERROR})

    def test_no_text_fields_exist_to_store_prompts(self):
        names = {f.name for f in AIPerformanceEvent._meta.fields}
        self.assertFalse(names & {"query", "answer", "prompt", "user"})

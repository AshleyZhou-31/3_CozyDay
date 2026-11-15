from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from .ai_cost import estimate_local_compute_cost
from .models import AIPerformanceEvent, AIResponseFeedback

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

    def test_simulated_cost_is_local_compute_from_generation_time(self):
        run()
        for event in AIPerformanceEvent.objects.filter(outcome=Outcome.SUCCESS):
            expected = estimate_local_compute_cost(event.generation_latency_ms / 1000)
            self.assertEqual(event.estimated_cost_usd, expected)

    def test_feedback_is_seeded_for_a_subset_of_successful_simulated_events(self):
        run()
        feedback = AIResponseFeedback.objects.all()
        successes = AIPerformanceEvent.objects.filter(outcome=Outcome.SUCCESS).count()
        self.assertGreater(feedback.count(), 0)
        self.assertLess(feedback.count(), successes)  # a subset, not every event
        self.assertTrue(all(f.event.is_simulated for f in feedback))
        self.assertTrue(all(f.event.outcome == Outcome.SUCCESS for f in feedback))
        self.assertEqual(
            set(feedback.values_list("rating", flat=True)),
            set(AIResponseFeedback.Rating.values),
        )

    def test_seeded_feedback_is_deterministic_and_not_duplicated(self):
        run("--seed", "7", "--count", "60")
        first = sorted(AIResponseFeedback.objects.values_list("rating", flat=True))
        run("--seed", "7", "--count", "60")
        second = sorted(AIResponseFeedback.objects.values_list("rating", flat=True))
        self.assertEqual(first, second)
        self.assertEqual(AIResponseFeedback.objects.count(), len(second))

    def test_real_feedback_is_never_touched(self):
        real = real_event()
        AIResponseFeedback.objects.create(event=real, rating="accurate")
        run()
        run("--clear")
        self.assertEqual(AIResponseFeedback.objects.count(), 1)
        self.assertTrue(AIResponseFeedback.objects.filter(event=real).exists())

    def test_clear_removes_simulated_feedback_with_its_events(self):
        run()
        run("--clear")
        self.assertEqual(AIResponseFeedback.objects.count(), 0)

    def test_no_text_fields_exist_to_store_prompts(self):
        names = {f.name for f in AIPerformanceEvent._meta.fields}
        self.assertFalse(names & {"query", "answer", "prompt", "user"})

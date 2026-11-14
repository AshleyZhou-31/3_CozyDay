"""Generate clearly labelled simulated AI analytics records for demonstrations.

Usage::

    python manage.py seed_ai_analytics            # replace simulated rows with 100 new ones
    python manage.py seed_ai_analytics --count 60
    python manage.py seed_ai_analytics --clear    # remove simulated rows only

Safety properties:

* Every record has ``is_simulated=True``; real records (``is_simulated`` False
  or null) are never created, changed or deleted by this command.
* It is repeatable: each run first removes the previous simulated records and
  then creates exactly ``--count`` new ones in one transaction, so running it
  again can never pile up duplicates.
* Output is deterministic for a given ``--seed``.
* No prompt, answer, retrieved text or user ID is generated or stored.

The values are illustrative, not measurements. Ranges follow the verified A9
evaluation (generation 3-21 s, embedding 0.015-0.04 s, retrieval <= 0.03 s,
in-scope best relevance 0.527-0.762, out-of-scope 0.02-0.18); input tokens
are based on the first real requests (about 890 each). All simulated
requests use the ``transformers-local`` backend because no other backend has
been measured, so the backend comparison stays honest.
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from planner.ai_cost import estimate_cost_usd
from planner.models import AIPerformanceEvent

DEFAULT_COUNT = 100
MAX_COUNT = 500
DEFAULT_SEED = 490
SPAN_DAYS = 14
MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"
BACKEND = "transformers-local"

CATEGORY_WEIGHTS = [
    (AIPerformanceEvent.QueryCategory.TASK_BREAKDOWN, 24),
    (AIPerformanceEvent.QueryCategory.PRIORITIZATION, 18),
    (AIPerformanceEvent.QueryCategory.STUDY_PLANNING, 22),
    (AIPerformanceEvent.QueryCategory.PRIVACY_SHARING, 10),
    (AIPerformanceEvent.QueryCategory.PROGRESS_REPORTING, 14),
    (AIPerformanceEvent.QueryCategory.OTHER, 12),
]
TEMPLATE_WEIGHTS = [("general", 40), ("weekly", 30), ("monthly", 18), ("three_month", 12)]
OUTCOME_WEIGHTS = [
    (AIPerformanceEvent.Outcome.SUCCESS, 80),
    (AIPerformanceEvent.Outcome.ABSTENTION, 15),
    (AIPerformanceEvent.Outcome.ERROR, 5),
]


def _pick(rng, weighted):
    values, weights = zip(*weighted)
    return rng.choices(values, weights=weights, k=1)[0]


def build_record(rng):
    """Return field values for one simulated request (without created_at)."""
    outcome = _pick(rng, OUTCOME_WEIGHTS)
    base = dict(
        endpoint="rag_planner",
        outcome=outcome,
        is_simulated=True,
        model_name=MODEL_NAME,
        serving_backend=BACKEND,
    )
    if outcome == AIPerformanceEvent.Outcome.ERROR:
        base.update(
            total_latency_ms=rng.randint(15, 250),
            validation_latency_ms=rng.randint(0, 5),
            retrieved_count=0,
        )
        return base

    category = _pick(rng, CATEGORY_WEIGHTS)
    embedding = rng.randint(15, 40)
    retrieval = rng.randint(2, 30)
    validation = rng.randint(1, 15)
    base.update(
        query_category=category,
        template_type=_pick(rng, TEMPLATE_WEIGHTS),
        query_length_chars=rng.randint(25, 220),
        retrieved_count=3,
        embedding_latency_ms=embedding,
        retrieval_latency_ms=retrieval,
        validation_latency_ms=validation,
    )
    if outcome == AIPerformanceEvent.Outcome.ABSTENTION:
        base.update(
            max_similarity_score=round(rng.uniform(0.02, 0.18), 3),
            generation_latency_ms=0,
            input_tokens_estimate=0,
            output_tokens_estimate=0,
            estimated_cost_usd=estimate_cost_usd(0, 0),
            total_latency_ms=embedding + retrieval + validation + rng.randint(2, 20),
        )
        return base

    output_tokens = rng.randint(90, 300)
    # Real prompts carry the template plus three retrieved chunks; the first real
    # requests measured about 890 input tokens each, so simulate around that.
    input_tokens = rng.randint(650, 1100)
    # Longer answers take longer: roughly 30-70 ms per generated token, which
    # keeps generation inside the 3-21 s range measured in the A9 evaluation.
    generation = min(21000, max(3000, int(output_tokens * rng.uniform(30, 70))))
    base.update(
        max_similarity_score=round(rng.uniform(0.527, 0.762), 3),
        generation_latency_ms=generation,
        input_tokens_estimate=input_tokens,
        output_tokens_estimate=output_tokens,
        estimated_cost_usd=estimate_cost_usd(input_tokens, output_tokens),
        total_latency_ms=embedding + retrieval + generation + validation + rng.randint(2, 30),
    )
    return base


class Command(BaseCommand):
    help = "Create (or remove) clearly labelled simulated AI analytics records."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                            help=f"Records to create (1-{MAX_COUNT}, default {DEFAULT_COUNT}).")
        parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                            help="Random seed; the same seed gives the same records.")
        parser.add_argument("--clear", action="store_true",
                            help="Only remove existing simulated records.")

    def handle(self, *args, **options):
        count = options["count"]
        if not options["clear"] and not 1 <= count <= MAX_COUNT:
            raise CommandError(f"--count must be between 1 and {MAX_COUNT}.")

        simulated = AIPerformanceEvent.objects.filter(is_simulated=True)
        if options["clear"]:
            removed, _ = simulated.delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {removed} simulated record(s)."))
            return

        rng = random.Random(options["seed"])
        now = timezone.now()
        with transaction.atomic():
            removed, _ = simulated.delete()
            for _ in range(count):
                values = build_record(rng)
                event = AIPerformanceEvent.objects.create(**values)
                created_at = now - timedelta(seconds=rng.randint(0, SPAN_DAYS * 86400 - 1))
                AIPerformanceEvent.objects.filter(pk=event.pk).update(created_at=created_at)

        self.stdout.write(self.style.SUCCESS(
            f"Replaced {removed} simulated record(s) with {count} new simulated record(s) "
            f"(is_simulated=True, backend {BACKEND}). Real records were not touched."
        ))

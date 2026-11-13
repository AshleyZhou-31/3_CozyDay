"""A9 Stage 3: evaluate the integrated AI RAG Planner through the real page.

Each case is POSTed to ``/planitems/ai-rag-planner/`` with Django's test
client as a throwaway logged-in user, so the evidence comes from the
integrated workflow (form validation -> view -> service adapter -> local
engine -> template), not from a notebook. Results are appended to a CSV so
an interrupted run can be resumed.

Needs the real models (about 6 GB download on first use). Never run it from
the automated test suite. Run it manually:

    python manage.py rag_evaluate
    python manage.py rag_evaluate --variants improved --cases Q1,Q3

``baseline`` switches both Stage 3 improvements off
(``AI_PLANNER_OUTPUT_VALIDATION=False``, ``AI_PLANNER_MIN_RELEVANCE=0``);
``improved`` is the shipped behaviour. Generation is greedy, so both
variants see the same raw model output where the model runs at all.
"""
import csv
import sys
import time
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings
from django.test.utils import setup_test_environment, teardown_test_environment
from django.urls import reverse

TEST_USERNAME = "rag_eval_user"
HOST = "localhost"
DEFAULT_MIN_RELEVANCE = 0.35

CASES = [
    ("Q1", "Break a large semester paper into tasks",
     "I have a big semester paper due in a few weeks. How should I break it down into tasks in CozyDay?",
     "Several small checkable steps (topic, sources, outline, draft, revise) with milestones, conservative estimates and dependencies."),
    ("Q2", "Prioritize several assignments due the same week",
     "I have three assignments due this week and they all feel urgent. How do I decide what to work on first?",
     "Start from the earliest firm deadline, estimate remaining work, split the biggest job, weigh consequences or renegotiate."),
    ("Q3", "Weekly study plan with spaced review",
     "How do I build a weekly study plan and prepare for my exam using spaced review?",
     "Start from fixed obligations and available time, spread review over several sessions with retrieval practice, keep slack."),
    ("Q4", "Share a group plan without exposing private details",
     "I want to share my group project plan with teammates. How do I do that without exposing private information?",
     "Share only deliverable/person/deadline, keep private notes out, check exports and privacy settings, use neutral titles."),
    ("Q5", "Use completion analytics for a progress report",
     "How should I use my task completion analytics to write a weekly progress report?",
     "Treat counts as descriptive not a measure of effort, compare with estimates/categories/trends, structure the report."),
]
PROBES = [
    ("X1", "Out-of-scope question (probe)",
     "What is the capital of France and who designed the Eiffel Tower?",
     "Should say CozyDay guidance does not cover this, not invent a planning answer."),
    ("X2", "Vague one-word input (probe)",
     "help",
     "Should ask for a specific planning question instead of generating a plan."),
]

FIELDS = [
    "case_id", "case", "variant", "query", "expected_behavior", "status", "error_message",
    "answer", "ends_cleanly", "warning", "retrieved_chunk_ids", "source_paragraph_ids",
    "similarity_scores", "retrieved_text_excerpts", "context_score", "answer_score",
    "key_points_stated", "abstained", "embedding_s", "retrieval_s", "generation_s", "total_s",
    "page_total_s",
]


def _scoring():
    a8 = Path(settings.BASE_DIR) / "a8_rag"
    if str(a8) not in sys.path:
        sys.path.insert(0, str(a8))
    import queries
    import scoring
    expected = {q["query_id"]: q["expected_evidence_ids"] for q in queries.TEST_QUERIES}
    return scoring, expected


class Command(BaseCommand):
    help = "Run the five Stage 3 evaluation cases (plus two probes) through the real RAG Planner page."

    def add_arguments(self, parser):
        parser.add_argument("--variants", default="baseline,improved")
        parser.add_argument("--cases", default="", help="Comma-separated ids, e.g. Q1,Q3 (default: all)")
        parser.add_argument("--no-probes", action="store_true")
        parser.add_argument("--out", default="docs/ai_stage3_evaluation/stage3_runs.csv")
        parser.add_argument("--force", action="store_true", help="Re-run rows already in the CSV")

    def handle(self, *args, **options):
        variants = [v.strip() for v in options["variants"].split(",") if v.strip()]
        if not set(variants) <= {"baseline", "improved"}:
            raise CommandError("--variants must be baseline, improved or both")
        cases = CASES + ([] if options["no_probes"] else PROBES)
        wanted = {c.strip() for c in options["cases"].split(",") if c.strip()}
        if wanted:
            cases = [c for c in cases if c[0] in wanted]

        out = Path(options["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        done = set()
        if out.exists() and not options["force"]:
            with out.open(newline="", encoding="utf-8") as handle:
                done = {(r["case_id"], r["variant"]) for r in csv.DictReader(handle)}

        from planner import rag_engine
        global DEFAULT_MIN_RELEVANCE
        DEFAULT_MIN_RELEVANCE = rag_engine.DEFAULT_MIN_RELEVANCE

        self.stdout.write("Loading models (first run downloads them; this can take several minutes)...")
        start = time.perf_counter()
        engine = rag_engine.get_engine()
        self.stdout.write(f"Models ready in {time.perf_counter() - start:.1f}s (not included in case latencies).")
        scoring, expected = _scoring()

        User = get_user_model()
        user, created = User.objects.get_or_create(username=TEST_USERNAME)
        if created:
            user.set_unusable_password()
            user.save()
        # Outside the test runner the client does not record template contexts;
        # this switches that recording on so the rendered page's data can be read.
        instrumented = False
        try:
            setup_test_environment()
            instrumented = True
        except RuntimeError:
            pass
        client = Client(SERVER_NAME=HOST)
        client.force_login(user)
        url = reverse("planner:ai-rag-planner")

        new_file = not out.exists() or options["force"]
        try:
            with out.open("w" if options["force"] else "a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
                if new_file:
                    writer.writeheader()
                for case_id, name, query, expectation in cases:
                    for variant in variants:
                        if (case_id, variant) in done:
                            self.stdout.write(f"skip {case_id} {variant} (already recorded)")
                            continue
                        self.stdout.write(f"run  {case_id} {variant} ...")
                        row = self._run_case(client, url, engine, scoring, expected,
                                             case_id, name, query, expectation, variant)
                        writer.writerow(row)
                        handle.flush()
                        self.stdout.write(
                            f"     status={row['status']} total={row['total_s']} "
                            f"clean={row['ends_cleanly']} ctx={row['context_score']} ans={row['answer_score']}"
                        )
        finally:
            if instrumented:
                teardown_test_environment()
            if created:
                user.delete()
        self.stdout.write(self.style.SUCCESS(f"Done. Results in {out}"))

    def _run_case(self, client, url, engine, scoring, expected, case_id, name, query, expectation, variant):
        row = {f: "" for f in FIELDS}
        row.update(case_id=case_id, case=name, variant=variant, query=query, expected_behavior=expectation)
        flag = variant == "improved"
        start = time.perf_counter()
        with override_settings(
            AI_PLANNER_OUTPUT_VALIDATION=flag,
            AI_PLANNER_MIN_RELEVANCE=DEFAULT_MIN_RELEVANCE if flag else 0.0,
            ALLOWED_HOSTS=[HOST, "testserver"],
        ):
            response = client.post(url, {"query": query})
        row["page_total_s"] = round(time.perf_counter() - start, 3)

        if response.context is None:
            raise CommandError("The page did not expose its template context; cannot record results.")
        result = response.context["result"] if response.context else None
        form = response.context["form"] if response.context else None
        if result is None:
            if form is not None and form.errors:
                row["status"] = "validation_error"
                row["error_message"] = " ".join(m for errs in form.errors.values() for m in errs)
            else:
                row["error_message"] = response.context["error_message"] if response.context else "no context"
                row["status"] = (
                    "validation_error"
                    if "could not format the plan correctly" in row["error_message"]
                    else "service_error"
                )
            return row

        row["status"] = "ok"
        answer = result["answer"]
        chunks = result["retrieved_chunks"]
        lookup = engine["chunk_lookup"]
        source_ids = []
        for chunk in chunks:
            for sid in lookup[chunk["id"]].get("source_ids", []):
                if sid not in source_ids:
                    source_ids.append(sid)
        stage = result.get("stage_latencies") or {}
        row.update(
            answer=answer,
            ends_cleanly=scoring.ends_cleanly(answer),
            warning=result.get("warning") or "",
            retrieved_chunk_ids=" | ".join(c["id"] for c in chunks),
            source_paragraph_ids=" | ".join(source_ids),
            similarity_scores=" | ".join(f"{c['score']:.3f}" for c in chunks),
            retrieved_text_excerpts=" || ".join(f"[{c['id']}] {c['text'][:300]}" for c in chunks),
            abstained=scoring.is_abstention(answer),
            embedding_s=round(stage.get("embedding", 0), 3),
            retrieval_s=round(stage.get("retrieval", 0), 3),
            generation_s=round(stage.get("generation", 0), 3),
            total_s=round(result["latency_seconds"], 3),
        )
        if case_id in expected:
            row["context_score"] = scoring.context_score(source_ids, expected[case_id])
            score, hit = scoring.answer_score(case_id, answer)
            row["answer_score"] = score
            row["key_points_stated"] = " | ".join(hit)
        return row

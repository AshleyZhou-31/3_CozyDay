"""Compare fixed public examples, saving each result as it completes.

This command never reads production requests or creates analytics events.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from planner.plan_templates import GENERAL, detect_plan_type
from planner.rag_engine import answer_query

SAMPLE_QUESTIONS = (
    "Help me plan a study week around reading, class, and writing time.",
    "I have one month to prepare a research proposal; help me break it into milestones.",
    "Build a three-month plan to finish a dissertation chapter.",
)


class Command(BaseCommand):
    help = "Compare general and specialized prompts on three fixed public questions."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="Save results as UTF-8 JSON after each case.")
        parser.add_argument("--max-time-seconds", type=int, default=None)

    def handle(self, *args, **options):
        timeout = options.get("max_time_seconds")
        if timeout is not None and timeout <= 0:
            raise CommandError("--max-time-seconds must be positive.")
        path = Path(options["output"]) if options.get("output") else None
        if path:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise CommandError("Could not create the output directory.") from exc
        results = []
        failed = False
        for index, query in enumerate(SAMPLE_QUESTIONS, start=1):
            for variant in (GENERAL, detect_plan_type(query)):
                self.stderr.write(f"Running sample {index}/3: {variant}")
                row = {"sample": index, "variant": variant}
                try:
                    kwargs = {"template_type": variant}
                    if timeout is not None:
                        kwargs["max_time_seconds"] = timeout
                    result = answer_query(query, **kwargs)
                    plan = result.get("structured_plan")
                    row.update(status="success" if plan is not None else "no_plan",
                               plan=plan, warning=result.get("warning"))
                    failed = failed or plan is None
                except Exception as exc:
                    row.update(status="error", error_type=type(exc).__name__,
                               plan=None, warning=None)
                    failed = True
                results.append(row)
                rendered = json.dumps(results, ensure_ascii=False, indent=2)
                if path:
                    try:
                        temporary = path.with_name(path.name + ".tmp")
                        temporary.write_text(rendered + "\n", encoding="utf-8")
                        temporary.replace(path)
                    except OSError as exc:
                        raise CommandError("Could not save comparison results.") from exc
                self.stderr.write(f"Completed sample {index}: {variant} ({row['status']})")
        self.stdout.write(rendered)
        if failed:
            raise CommandError("Comparison contains failed or abstained cases; inspect the results.")

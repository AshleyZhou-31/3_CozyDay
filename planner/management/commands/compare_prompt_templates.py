"""Compare general and specialized prompt outputs on fixed sample questions.

Run with the local model available. Results are printed to the terminal only;
the command does not create analytics events or save the sample questions.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from planner.plan_templates import GENERAL, detect_plan_type
from planner.rag_engine import answer_query


SAMPLE_QUESTIONS = (
    "Help me plan a study week around reading, class, and writing time.",
    "I have one month to prepare a research proposal; help me break it into milestones.",
    "Build a three-month plan to finish a dissertation chapter.",
)


class Command(BaseCommand):
    help = "Compare general and detected plan templates on three representative questions."

    def handle(self, *args, **options):
        results = []
        try:
            for index, query in enumerate(SAMPLE_QUESTIONS, start=1):
                selected_type = detect_plan_type(query)
                for template_type in (GENERAL, selected_type):
                    result = answer_query(query, template_type=template_type)
                    results.append({
                        "sample": index,
                        "variant": template_type,
                        "plan": result.get("structured_plan"),
                        "warning": result.get("warning"),
                    })
        except Exception as exc:
            raise CommandError(
                f"Template comparison could not complete ({type(exc).__name__})."
            ) from exc
        self.stdout.write(json.dumps(results, ensure_ascii=False, indent=2))

"""Stage 2 real local smoke test: one actual (not mocked) call through the
local RAG engine, loading the real MPNet embedding model and the real
Qwen2.5-3B-Instruct generation model.

Downloads ~0.5GB (MPNet) plus ~6GB (Qwen2.5-3B) of model weights on first
run and needs real memory/time. Never run this from the automated test
suite; run it manually:

    python manage.py rag_smoke_test
    python manage.py rag_smoke_test --query "How do I plan a weekly study schedule?"
"""
from django.core.management.base import BaseCommand

from planner.rag_planner import RAGPlannerError, generate_rag_plan

DEFAULT_QUERY = (
    "I have a big semester paper due in a few weeks. How should I break it down into tasks?"
)


class Command(BaseCommand):
    help = "Run one real (non-mocked) local RAG request end to end and print the result."

    def add_arguments(self, parser):
        parser.add_argument("--query", default=DEFAULT_QUERY)

    def handle(self, *args, **options):
        query = options["query"]
        self.stdout.write(f"Query: {query}")
        try:
            result = generate_rag_plan(query)
        except RAGPlannerError as exc:
            self.stderr.write(self.style.ERROR(f"RAG request failed: {exc.user_message}"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("\nAnswer:"))
        self.stdout.write(result["answer"])
        self.stdout.write(f"\nLatency: {result['latency_seconds']:.3f}s")
        if result["warning"]:
            self.stdout.write(self.style.WARNING(f"Warning: {result['warning']}"))
        self.stdout.write("\nRetrieved chunks:")
        for chunk in result["retrieved_chunks"]:
            score = f"{chunk['score']:.3f}" if chunk["score"] is not None else "n/a"
            self.stdout.write(f"  [{chunk['id']}] score={score}  {chunk['text'][:100]}")

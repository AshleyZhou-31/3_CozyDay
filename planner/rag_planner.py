"""Temporary Stage 1 adapter for the local RAG Planner page contract.

Stage 2 replaces this implementation with the local retrieval and generation
pipeline. Keep the function signature and response fields stable so that the
Django view and template do not need to change.
"""


class RAGPlannerError(Exception):
    """A safe, user-facing error raised by the RAG service adapter."""

    user_message = "The planning assistant could not complete your request. Please try again."

    def __init__(self, user_message=None):
        if user_message:
            self.user_message = user_message
        super().__init__(self.user_message)


def generate_rag_plan(query, user=None):
    """Return a clearly labeled mock result matching the Stage 2 contract.

    ``user`` is accepted for a future user-scoped retrieval implementation;
    this placeholder neither reads nor returns personal user data.
    """
    del query, user
    return {
        "answer": (
            "A local planning answer will appear here after the RAG service is "
            "connected. The finished assistant will use retrieved CozyDay "
            "planning guidance to suggest actionable next steps."
        ),
        "retrieved_chunks": [
            {
                "id": "STAGE1-MOCK",
                "text": "Placeholder source shown to verify the Django result layout; no knowledge-base retrieval has run.",
                "score": None,
            }
        ],
        "latency_seconds": 0.0,
        "warning": "Stage 1 mock response only. The local RAG model is not connected yet.",
    }

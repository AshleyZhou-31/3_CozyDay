"""Stage 2: local RAG Planner service adapter.

Thin wrapper preserving the Stage 1 page contract
(``generate_rag_plan(query, user=None) -> {"answer", "retrieved_chunks",
"latency_seconds", "warning"}``) while delegating the real work to
:mod:`planner.rag_engine`: local MPNet embeddings, hybrid-chunking cosine
retrieval, and the locked Qwen2.5-3B-Instruct generation pipeline, all
adapted from the team's A8 RAG assignment.

``rag_engine`` (and the torch/transformers/sentence-transformers it needs)
is imported lazily inside the function body, not at module load time, so
importing this module -- and therefore Django starting up, and the normal
test suite running -- never pulls in or downloads anything heavy.
"""


class RAGPlannerError(Exception):
    """A safe, user-facing error raised by the RAG service adapter."""

    user_message = "The planning assistant could not complete your request. Please try again."

    def __init__(self, user_message=None):
        if user_message:
            self.user_message = user_message
        super().__init__(self.user_message)


def generate_rag_plan(query, user=None):
    """Run the local RAG pipeline and return the Stage 1 page contract.

    All failures are normalised to ``RAGPlannerError`` subclasses carrying a
    safe ``user_message``; the Django view never sees a raw model or library
    exception, and the user's query text is never logged.
    """
    from . import rag_engine

    result = rag_engine.answer_query(query, user=user)
    response = {
        "answer": result["answer"],
        "retrieved_chunks": result["retrieved_chunks"],
        "latency_seconds": result["latency_seconds"],
        "warning": result["warning"],
    }
    if result.get("stage_latencies"):
        response["stage_latencies"] = result["stage_latencies"]
    return response

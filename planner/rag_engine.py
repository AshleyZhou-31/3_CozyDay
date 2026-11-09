"""Stage 2: local RAG engine for the CozyDay AI Planner.

Adapts A8's knowledge base, hybrid chunking, MPNet (all-mpnet-base-v2, 768d)
embeddings, cosine-similarity retrieval, and the locked Qwen2.5-3B-Instruct
generation pipeline (see ``a8_rag/``) into one lazily-loaded, process-cached
Django service module, per the team's locked technical choices in
``CozyDay_Django_AI_Integration_Team_Work_and_Demo_Plan``.

Design notes
------------
* ``a8_rag/`` is added to ``sys.path`` rather than imported as
  ``a8_rag.*``, because its own modules use flat sibling imports
  (``from embedding import embed_query``). This file never edits a8_rag's
  already-reviewed-and-merged code.
* Heavy imports (torch, transformers, sentence_transformers, numpy,
  scikit-learn) and the model loads happen only inside functions, behind the
  lazy singleton in ``get_engine()``. Django startup and the normal
  (mocked) test suite never import or download anything.
* Every failure surfaces as a ``RAGPlannerError`` subclass with a safe
  ``user_message``; callers never see a raw model/library traceback, and
  the user's query text is never logged.
* Repeated requests reuse the same in-process embedding/generation models
  and the same cached chunk embeddings; nothing is reloaded per request.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import threading
import time
from pathlib import Path

from django.conf import settings

from .rag_planner import RAGPlannerError

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
A8_RAG_DIR = BASE_DIR / "a8_rag"
if str(A8_RAG_DIR) not in sys.path:
    sys.path.insert(0, str(A8_RAG_DIR))

# Locked technical choices (CozyDay_Django_AI_Integration_Team_Work_and_Demo_Plan,
# section 1): all-mpnet-base-v2 / 768d embeddings, hybrid chunking, Top-K 3,
# Qwen2.5-3B-Instruct generation. See docs/ai_integration_model_rationale.md
# for the measured A8 evidence behind each choice.
EMBEDDING_MODEL_KEY = "medium"
CHUNK_STRATEGY = "hybrid"
TOP_K = 3
# Bump this if chunking.py's hybrid-strategy logic itself changes (not just
# the knowledge base content, which _corpus_hash already covers), so a stale
# cache built under the old chunking rules is never reused silently.
CHUNKING_VERSION = "a8-hybrid-v1"

CACHE_DIR = Path(__file__).resolve().parent / "rag_cache"
CACHE_VECTORS_PATH = CACHE_DIR / "mpnet_hybrid_embeddings.npy"
CACHE_META_PATH = CACHE_DIR / "mpnet_hybrid_embeddings_meta.json"


class RAGUnavailableError(RAGPlannerError):
    user_message = (
        "The local planning assistant is not available right now. Ask the site "
        "owner to check that the AI packages and models are installed."
    )


class RAGRetrievalError(RAGPlannerError):
    user_message = "The planning assistant could not search its knowledge base. Please try again."


class RAGGenerationError(RAGPlannerError):
    user_message = "The planning assistant ran into a problem generating a response. Please try again."


class RAGOutputError(RAGPlannerError):
    user_message = (
        "The planning assistant did not return a usable answer. Please try rewording your question."
    )


def _setting(name, default):
    return getattr(settings, name, default)


def _corpus_hash(records):
    """Hash paragraph id+title+text, so any content edit is caught even if
    chunk IDs happen to stay the same (ID matching alone would miss that)."""
    payload = json.dumps(
        [{"id": r["id"], "title": r.get("title", ""), "body": r["body"]} for r in records],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Lazy, process-cached engine
# --------------------------------------------------------------------------
_engine = None
_engine_error = None
_load_lock = threading.Lock()
_generate_lock = threading.Lock()


def clear_engine_cache():
    """Drop the cached engine and any cached load failure (used by tests)."""
    global _engine, _engine_error
    _engine = None
    _engine_error = None


def _build_engine():
    try:
        from chunking import build_all_chunks, load_knowledge_base
        from embedding import load_embedding_model
        from generation import load_generation_model
        from retrieval import build_chunk_lookup
    except ImportError as exc:
        logger.warning("RAG engine packages are missing: %s", exc)
        raise RAGUnavailableError() from exc

    try:
        records = load_knowledge_base()
        chunks_by_strategy = build_all_chunks(records)
        chunks = chunks_by_strategy[CHUNK_STRATEGY]
        chunk_lookup = build_chunk_lookup(chunks_by_strategy)[CHUNK_STRATEGY]

        embedding_info = load_embedding_model(EMBEDDING_MODEL_KEY)
        vectors = _load_or_build_embeddings(embedding_info, chunks, records)

        generation_info = load_generation_model()
    except RAGPlannerError:
        raise
    except Exception as exc:
        logger.exception("Could not build the local RAG engine")
        raise RAGUnavailableError(
            "The local RAG models could not be loaded (check network, disk space, "
            "and memory). Please try again later."
        ) from exc

    return {
        "chunk_ids": vectors["chunk_ids"],
        "vectors": vectors["vectors"],
        "chunk_lookup": chunk_lookup,
        "embedding_info": embedding_info,
        "generation_info": generation_info,
    }


def _load_or_build_embeddings(embedding_info, chunks, records):
    import numpy as np

    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    corpus_hash = _corpus_hash(records)

    if CACHE_VECTORS_PATH.exists() and CACHE_META_PATH.exists():
        meta = json.loads(CACHE_META_PATH.read_text())
        if (
            meta.get("model_name") == embedding_info["model_name"]
            and meta.get("chunking_version") == CHUNKING_VERSION
            and meta.get("corpus_hash") == corpus_hash
            and meta.get("chunk_ids") == chunk_ids
        ):
            vectors = np.load(CACHE_VECTORS_PATH)
            if vectors.shape[0] == len(chunk_ids):
                return {"chunk_ids": chunk_ids, "vectors": vectors}
        logger.info("RAG embedding cache is stale (model/corpus/chunking changed); recomputing.")

    texts = [chunk["text"] for chunk in chunks]
    vectors = embedding_info["model"].encode(
        texts, convert_to_numpy=True, normalize_embeddings=True
    ).astype("float32")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(CACHE_VECTORS_PATH, vectors)
    CACHE_META_PATH.write_text(json.dumps({
        "model_name": embedding_info["model_name"],
        "chunking_version": CHUNKING_VERSION,
        "corpus_hash": corpus_hash,
        "chunk_ids": chunk_ids,
    }, indent=2))
    return {"chunk_ids": chunk_ids, "vectors": vectors}


def get_engine():
    """Return the cached engine, building (and loading all models) on first use.

    A failed build is cached too (not retried on every request) but can be
    cleared with ``clear_engine_cache()``.
    """
    global _engine, _engine_error
    if _engine is not None:
        return _engine
    if _engine_error is not None:
        raise _engine_error
    with _load_lock:
        if _engine is not None:
            return _engine
        if _engine_error is not None:
            raise _engine_error
        try:
            _engine = _build_engine()
        except RAGPlannerError as exc:
            _engine_error = exc
            raise
        return _engine


# --------------------------------------------------------------------------
# Request pipeline
# --------------------------------------------------------------------------
def answer_query(query, user=None, top_k=None, max_time_seconds=None):
    """Run the full retrieve-then-generate pipeline for one validated query.

    Returns ``{"answer", "retrieved_chunks", "latency_seconds", "warning"}``
    matching the Stage 1 page contract. ``user`` is accepted for a future
    user-scoped retrieval extension; this implementation does not yet read
    or return any user-specific data.
    """
    del user
    top_k = top_k or TOP_K
    max_time_seconds = max_time_seconds or _setting("AI_PLANNER_MAX_TIME_SECONDS", 120)
    engine = get_engine()

    start_total = time.perf_counter()
    try:
        if engine["chunk_ids"]:
            from embedding import embed_query
            from retrieval import similarity_search

            query_vector, embedding_latency = embed_query(engine["embedding_info"], query)
            ranked, retrieval_latency = similarity_search(
                query_vector, engine["chunk_ids"], engine["vectors"], top_k=top_k
            )
        else:
            # sklearn's cosine_similarity rejects a zero-row corpus outright;
            # an empty knowledge base is a "no results" case, not a crash.
            ranked = []
            embedding_latency = retrieval_latency = 0.0
    except Exception as exc:
        logger.exception("RAG retrieval failed")
        raise RAGRetrievalError() from exc

    chunk_lookup = engine["chunk_lookup"]
    retrieval_chunks = [
        {"chunk_id": row["chunk_id"], "text": chunk_lookup[row["chunk_id"]]["text"], "score": row["score"]}
        for row in ranked
    ]
    response_chunks = [
        {"id": chunk["chunk_id"], "text": chunk["text"], "score": chunk["score"]}
        for chunk in retrieval_chunks
    ]

    warning = None
    if not response_chunks:
        warning = "No closely matching CozyDay guidance was found; this answer may be general."

    min_relevance = _setting("AI_PLANNER_MIN_RELEVANCE", DEFAULT_MIN_RELEVANCE)
    if response_chunks and max(c["score"] for c in response_chunks) < min_relevance:
        # Retrieval found nothing relevant: do not let the model answer from
        # general knowledge or from unrelated chunks. The chunks are still
        # returned so the user and reviewers can see how weak the match was.
        best = max(c["score"] for c in response_chunks)
        return {
            "answer": OUT_OF_SCOPE_ANSWER,
            "retrieved_chunks": response_chunks,
            "latency_seconds": time.perf_counter() - start_total,
            "warning": f"No closely matching CozyDay guidance was found (best relevance {best:.2f}).",
            "stage_latencies": {
                "embedding": embedding_latency,
                "retrieval": retrieval_latency,
                "generation": 0.0,
            },
        }

    try:
        answer, generation_latency, timed_out = _generate_with_timeout(
            engine["generation_info"], retrieval_chunks, query, max_time_seconds
        )
    except RAGPlannerError:
        raise
    except Exception as exc:
        logger.exception("RAG generation failed")
        raise RAGGenerationError() from exc

    if timed_out:
        raise RAGGenerationError(
            "The planning assistant took too long to respond. Please try a shorter question."
        )
    if not answer or not answer.strip():
        raise RAGOutputError()

    answer = answer.strip()
    if _setting("AI_PLANNER_OUTPUT_VALIDATION", True):
        answer, answer_warning = finalize_answer(answer)
        warning = warning or answer_warning

    total_latency = time.perf_counter() - start_total
    return {
        "answer": answer,
        "retrieved_chunks": response_chunks,
        "latency_seconds": total_latency,
        "warning": warning,
        "stage_latencies": {
            "embedding": embedding_latency,
            "retrieval": retrieval_latency,
            "generation": generation_latency,
        },
    }


# Chosen from the Stage 3 evaluation: in-scope questions had a best-chunk
# similarity of 0.527-0.762, the out-of-scope probe 0.040 and the vague
# one-word probe 0.183. 0.35 sits in the gap; set the setting to 0 to disable.
DEFAULT_MIN_RELEVANCE = 0.35
OUT_OF_SCOPE_ANSWER = (
    "CozyDay's planning guidance does not contain enough information to answer that. "
    "Try asking about breaking a big task into steps, deciding what to do first, "
    "building a weekly study plan, sharing a plan without private details, or "
    "writing a progress report."
)

TRUNCATION_WARNING = (
    "This answer reached the length limit, so the unfinished last part was removed. "
    "Ask a narrower question to see the rest."
)
_SENTENCE_END_CHARS = ".!?)\"'\u201d"
_MIN_KEPT_FRACTION = 0.25


def finalize_answer(answer):
    """Output validation: never show a sentence cut off by the token limit.

    The locked generation step stops at ``max_new_tokens`` even mid-sentence.
    If the text does not end on terminal punctuation, drop the unfinished
    tail back to the last finished sentence or list item and return a
    warning. If no usable finished part remains (nothing ends before 25% of
    the text), keep the full text and still warn. Complete answers are
    returned unchanged with no warning.
    """
    text = (answer or "").strip()
    if not text or text[-1] in _SENTENCE_END_CHARS:
        return text, None
    sentence_ends = [text.rfind(mark) + 1 for mark in (". ", "! ", "? ")]
    cut = max(sentence_ends + [text.rfind("\n")])
    if cut < len(text) * _MIN_KEPT_FRACTION:
        return text, TRUNCATION_WARNING
    kept = re.sub(r"(?:^|\s)\d{1,2}\.$", "", text[:cut].rstrip()).rstrip()
    return kept, TRUNCATION_WARNING


def _generate_with_timeout(generation_info, chunks, query, max_time_seconds):
    """Run ``generation.generate_answer`` on a worker thread with a soft timeout.

    a8_rag.generation's decoding settings stay locked and unmodified; this
    only bounds how long the Django request waits for one call, and
    serializes generation calls against the single shared model instance.

    The executor is deliberately NOT used as a context manager.
    ThreadPoolExecutor.__exit__ calls shutdown(wait=True), which blocks
    until the submitted task finishes -- even after future.result() has
    already raised TimeoutError. That would make this "soft timeout" a
    no-op: the caller would still block for however long the real
    (possibly-stuck) generation call takes. shutdown(wait=False) lets this
    function return promptly on timeout instead; the abandoned worker
    thread keeps running to completion in the background, which is the
    known limitation already documented in
    docs/ai_integration_model_rationale.md (Python cannot safely kill a
    running model.generate() call from another thread).
    """
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FutureTimeoutError

    from generation import generate_answer

    def _run():
        with _generate_lock:
            return generate_answer(generation_info, chunks, query)

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_run)
    try:
        answer, latency = future.result(timeout=max_time_seconds)
        return answer, latency, False
    except FutureTimeoutError:
        logger.warning("RAG generation exceeded the %.0fs soft timeout", max_time_seconds)
        return "", max_time_seconds, True
    finally:
        pool.shutdown(wait=False)

"""CozyDay Stage 2: single run_rag interface tying embedding, retrieval, and
generation together, plus the nine-combination smoke test runner.
"""
from __future__ import annotations

import time

from generation import generate_answer
from retrieval import retrieve


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def run_rag(query, model_info, strategy, embeddings, chunk_lookup, generation_info, top_k=3):
    """Full pipeline for one (query, embedding model, chunking strategy) combination.

    Returns retrieved chunks, the final answer, and embedding/retrieval/
    generation/total latency. Reuses the one locked generation model and
    decoding settings for every call; callers must not vary those between
    experiments.
    """
    start_total = time.perf_counter()
    retrieval_result = retrieve(query, model_info, strategy, embeddings, chunk_lookup, top_k=top_k)
    answer, generation_latency = generate_answer(generation_info, retrieval_result['chunks'], query)
    total_latency = time.perf_counter() - start_total

    return {
        'query': query,
        'model_key': model_info['key'],
        'strategy': strategy,
        'top_k': top_k,
        'retrieved_chunks': retrieval_result['chunks'],
        'final_answer': answer,
        'embedding_latency_seconds': retrieval_result['embedding_latency_seconds'],
        'retrieval_latency_seconds': retrieval_result['retrieval_latency_seconds'],
        'generation_latency_seconds': generation_latency,
        'total_latency_seconds': total_latency,
    }


def run_smoke_test(query, model_infos, chunks_by_strategy, embeddings, chunk_lookup,
                    generation_info, top_k=3):
    """Run one query across all nine (embedding model x chunking strategy) combinations.

    Returns a list of nine run_rag results, one per combination, each
    carrying its own retrieved chunks and final answer so every combination
    can be displayed, not only summarized.
    """
    results = []
    for model_key, model_info in model_infos.items():
        for strategy in chunks_by_strategy:
            results.append(run_rag(query, model_info, strategy, embeddings, chunk_lookup,
                                    generation_info, top_k=top_k))
    _require(len(results) == 9, f'Expected 9 smoke-test runs, got {len(results)}')
    return results

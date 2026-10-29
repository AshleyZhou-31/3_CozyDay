"""CozyDay Stage 2: cosine-similarity retrieval over cached chunk embeddings."""
from __future__ import annotations

import time

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from embedding import embed_query


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def build_chunk_lookup(chunks_by_strategy):
    """{strategy: {chunk_id: chunk_dict}}; turns a retrieved ID back into full chunk text."""
    return {strategy: {chunk['chunk_id']: chunk for chunk in chunks}
            for strategy, chunks in chunks_by_strategy.items()}


def similarity_search(query_vector, chunk_ids, vectors, top_k=3):
    """Rank cached chunk vectors against one normalized query vector.

    Vectors are already L2-normalized at embedding time, so cosine similarity
    equals their dot product; scikit-learn's cosine_similarity is used
    directly so the searchable structure explicitly satisfies the
    assignment's NumPy/scikit-learn/FAISS requirement rather than relying
    silently on that normalization.
    """
    _require(top_k >= 1, 'top_k must be at least 1')
    _require(len(chunk_ids) == vectors.shape[0], 'chunk_ids/vectors length mismatch')
    start = time.perf_counter()
    scores = cosine_similarity(query_vector.reshape(1, -1), vectors)[0]
    k = min(top_k, len(chunk_ids))
    order = np.argsort(-scores)[:k]
    results = [{'chunk_id': chunk_ids[i], 'score': float(scores[i])} for i in order]
    latency = time.perf_counter() - start
    return results, latency


def retrieve(query, model_info, strategy, embeddings, chunk_lookup, top_k=3):
    """Single consistent retrieval entry point for every experiment.

    Accepts the query text, an embedding-model info dict (as returned by
    embedding.load_embedding_model), a chunking strategy name, and Top-K.
    Returns chunk IDs, complete chunk text, similarity scores, and latency
    (both the query-embedding latency and the similarity-search latency, so
    callers such as run_rag can report them separately).
    """
    model_key = model_info['key']
    _require(model_key in embeddings, f'Unknown embedding model key: {model_key}')
    _require(strategy in embeddings[model_key], f'Unknown strategy: {strategy}')
    cached = embeddings[model_key][strategy]

    query_vector, embedding_latency = embed_query(model_info, query)
    ranked, retrieval_latency = similarity_search(query_vector, cached['chunk_ids'],
                                                   cached['vectors'], top_k=top_k)

    lookup = chunk_lookup[strategy]
    chunks = [{'chunk_id': row['chunk_id'], 'text': lookup[row['chunk_id']]['text'],
               'score': row['score']} for row in ranked]

    return {
        'query': query,
        'model_key': model_key,
        'strategy': strategy,
        'top_k': top_k,
        'chunks': chunks,
        'embedding_latency_seconds': embedding_latency,
        'retrieval_latency_seconds': retrieval_latency,
    }

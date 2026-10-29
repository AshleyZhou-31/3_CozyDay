"""CozyDay Stage 2: sentence-transformer embedding pipeline.

Loads the three assignment-approved embedding models, embeds every chunk
produced by Stage 1's three chunking strategies, and caches the resulting
vectors to disk so later notebook cells and other modules do not recompute
them. No model weights or caches are committed; only this module and the
small JSON/`.npy` cache files it writes under results/embeddings/ are.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
EMBEDDINGS_DIR = RESULTS_DIR / 'embeddings'

# The three sentence-transformers models fixed by the team's shared contract.
EMBEDDING_MODELS = {
    'small': 'sentence-transformers/all-MiniLM-L6-v2',
    'medium': 'sentence-transformers/all-mpnet-base-v2',
    'large': 'BAAI/bge-large-en-v1.5',
}
EXPECTED_DIMENSIONS = {'small': 384, 'medium': 768, 'large': 1024}
_PROBE_TEXT = 'CozyDay embedding dimension probe.'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def pick_device(preferred=None):
    """Return the best available torch device: cuda, then mps, then cpu.

    Unlike A7's deliberately cpu/cuda-only contract, Stage 2 has no such
    restriction, so this also uses Apple Silicon's mps backend when available.
    """
    import torch
    if preferred is not None:
        return preferred
    if torch.cuda.is_available():
        return 'cuda'
    if getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
        return 'mps'
    return 'cpu'


def load_embedding_model(key, device=None):
    """Load one approved embedding model; record name, dimension, device, load time.

    Raises ValueError if the model's actual output dimension does not match
    the assignment's expected dimensionality for this model key.
    """
    _require(key in EMBEDDING_MODELS, f'Unknown embedding model key: {key}')
    from sentence_transformers import SentenceTransformer

    model_name = EMBEDDING_MODELS[key]
    resolved_device = pick_device(device)
    start = time.perf_counter()
    model = SentenceTransformer(model_name, device=resolved_device)
    load_time = time.perf_counter() - start

    probe = model.encode([_PROBE_TEXT], convert_to_numpy=True, normalize_embeddings=True)
    actual_dim = int(probe.shape[1])
    _require(actual_dim == EXPECTED_DIMENSIONS[key],
              f'{model_name}: expected {EXPECTED_DIMENSIONS[key]} dims, got {actual_dim}')

    return {
        'key': key,
        'model_name': model_name,
        'model': model,
        'dimension': actual_dim,
        'device': resolved_device,
        'load_time_seconds': load_time,
    }


def load_all_embedding_models(device=None):
    """Load all three approved models; returns {key: model_info} in a fixed order."""
    return {key: load_embedding_model(key, device=device) for key in EMBEDDING_MODELS}


def describe_models(model_infos):
    """Flat rows of {key, model_name, dimension, device, load_time_seconds} for display."""
    return [{'key': info['key'], 'model_name': info['model_name'], 'dimension': info['dimension'],
             'device': info['device'], 'load_time_seconds': info['load_time_seconds']}
            for info in model_infos.values()]


def _cache_paths(model_key, strategy):
    base = EMBEDDINGS_DIR / f'{model_key}__{strategy}'
    return base.with_suffix('.npy'), base.with_suffix('.json')


def _load_cached(model_key, strategy, chunks):
    vectors_path, meta_path = _cache_paths(model_key, strategy)
    if not (vectors_path.exists() and meta_path.exists()):
        return None
    meta = json.loads(meta_path.read_text())
    expected_ids = [chunk['chunk_id'] for chunk in chunks]
    if meta.get('chunk_ids') != expected_ids:
        return None
    if meta.get('model_name') != EMBEDDING_MODELS[model_key]:
        return None
    vectors = np.load(vectors_path)
    if vectors.shape != (len(expected_ids), EXPECTED_DIMENSIONS[model_key]):
        return None
    return {'chunk_ids': expected_ids, 'vectors': vectors, 'meta': meta}


def _save_cache(model_key, strategy, chunk_ids, vectors, model_name, embed_time):
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    vectors_path, meta_path = _cache_paths(model_key, strategy)
    np.save(vectors_path, vectors)
    meta_path.write_text(json.dumps({
        'model_key': model_key, 'model_name': model_name, 'strategy': strategy,
        'chunk_ids': chunk_ids, 'dimension': int(vectors.shape[1]),
        'embed_time_seconds': embed_time,
    }, indent=2))


def embed_chunks(model_info, chunks, strategy, use_cache=True):
    """Embed one (model, strategy) combination; load from a valid cache instead.

    Returns {'chunk_ids', 'vectors' (float32, L2-normalized, shape [n, dim]),
    'embed_time_seconds', 'from_cache'}.
    """
    model_key = model_info['key']
    if use_cache:
        cached = _load_cached(model_key, strategy, chunks)
        if cached is not None:
            return {'chunk_ids': cached['chunk_ids'], 'vectors': cached['vectors'],
                    'embed_time_seconds': cached['meta'].get('embed_time_seconds', 0.0),
                    'from_cache': True}

    texts = [chunk['text'] for chunk in chunks]
    chunk_ids = [chunk['chunk_id'] for chunk in chunks]
    start = time.perf_counter()
    vectors = model_info['model'].encode(texts, convert_to_numpy=True,
                                          normalize_embeddings=True).astype('float32')
    embed_time = time.perf_counter() - start

    if use_cache:
        _save_cache(model_key, strategy, chunk_ids, vectors, model_info['model_name'], embed_time)

    return {'chunk_ids': chunk_ids, 'vectors': vectors, 'embed_time_seconds': embed_time,
            'from_cache': False}


def embed_all_combinations(model_infos, chunks_by_strategy, use_cache=True):
    """Embed every (embedding model x chunking strategy) combination (3 x 3 = 9).

    Returns embeddings[model_key][strategy] = {'chunk_ids', 'vectors',
    'embed_time_seconds', 'from_cache'}.
    """
    embeddings = {}
    for model_key, model_info in model_infos.items():
        embeddings[model_key] = {}
        for strategy, chunks in chunks_by_strategy.items():
            embeddings[model_key][strategy] = embed_chunks(model_info, chunks, strategy,
                                                            use_cache=use_cache)
    return embeddings


def embed_query(model_info, query):
    """Embed a single query string with the same normalization as stored chunks."""
    _require(isinstance(query, str) and query.strip(), 'Query must be a nonempty string')
    start = time.perf_counter()
    vector = model_info['model'].encode([query], convert_to_numpy=True,
                                         normalize_embeddings=True).astype('float32')[0]
    latency = time.perf_counter() - start
    return vector, latency


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from chunking import build_all_chunks, load_knowledge_base

    records = load_knowledge_base()
    chunks_by_strategy = build_all_chunks(records)
    model_infos = load_all_embedding_models()
    print('Loaded embedding models:')
    for row in describe_models(model_infos):
        print(' ', row)

    embeddings = embed_all_combinations(model_infos, chunks_by_strategy)
    for model_key, by_strategy in embeddings.items():
        for strategy, result in by_strategy.items():
            status = 'cached' if result['from_cache'] else f"{result['embed_time_seconds']:.3f}s"
            print(model_key, strategy, result['vectors'].shape, status)

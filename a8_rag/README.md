# CozyDay — P1 A8, Stage 1 (Lin Gao)

This package implements **only** Step 1.1 (knowledge base), Step 1.2 (three text chunking methods), and the reproducibility foundation. Stages 2–4 (embeddings, retrieval, generation, experiments, and system design) are intentionally **not implemented**.

## Quick start

From the directory containing these files:

```bash
python chunking.py
python test_stage1.py
python -m pip install -r requirements.txt
jupyter notebook rag_system.ipynb
```

Python 3.9+ recommended. No API credentials, GPU, or embedding models are required for Stage 1.

## Files

- `data/cozyday_knowledge_base.json`: 30 original paragraphs; immutable IDs `P001`–`P030`; each record has `id`, `title`, `topic`, and `body`.
- `chunking.py`: all deterministic Stage 1 loading, chunking, and validation functions.
- `test_stage1.py`: automated standalone regression tests.
- `rag_system.ipynb`: Stage 1 demonstrations and saved outputs; Stage 2 handoff note.
- `rag_analysis.md`: methodological details, count summary, and documented limitations.

## Stage 2 interface (freeze this contract)

```python
from chunking import load_knowledge_base, validate_knowledge_base, build_all_chunks
records = load_knowledge_base()
summary = validate_knowledge_base(records)
chunks_by_strategy = build_all_chunks(records)
chunks = chunks_by_strategy['fixed']  # also 'overlap', 'hybrid'
```

Individual chunk schema:

```json
{"chunk_id":"FIXED_001", "strategy":"fixed", "source_ids":["P001"], "topic":"mixed", "text":"Full text...", "word_count":130}
```

`chunk_id` and `source_ids` are stable for the frozen dataset and parameter choices. **Embed `chunk['text']`**, and preserve the other fields for retrieval diagnostics.

Default options: `fixed_length_chunks(records, target_words=130)`, `overlapping_paragraph_chunks(records, window=2, stride=1)`, and `hybrid_topic_chunks(records, max_words=230)`.

All paths are relative to the module location, not a particular local user's directory. Never commit model weights, tokens, caches, or `.venv/`.

**Integration note:** If the repository already contains root-level `README.md` or `requirements.txt`, merge these Stage 1 sections into the existing files rather than replacing other contributors' content. This is a self-contained handoff package, not an assertion that the remote repository has been updated.

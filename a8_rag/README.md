# CozyDay — P1 A8, Stage 1 (Lin Gao)

Implements Step 1.1 (knowledge base), Step 1.2 (three chunking strategies), automated validation, and the Stage 2 handoff. Embeddings, retrieval, generation, experiments, and system design belong to later stages.

## Setup and verification

Use Python **3.11+** (verified with Python 3.12). From the repository root:

```bash
cd a8_rag
python -m pip install -r requirements.txt
python -m pip check
python chunking.py
python test_stage1.py
jupyter nbconvert --to notebook --execute rag_system.ipynb --output rag_system_verified.ipynb
jupyter notebook rag_system.ipynb
```

The executed verification copy is ignored by Git; do not include it in the PR or final ZIP. To update the canonical notebook after intentional changes, run `jupyter nbconvert --to notebook --execute --inplace rag_system.ipynb` and inspect its outputs. Save the full representative chunks, not truncated previews.

Only notebook tooling needs installation. Chunking and unit tests use the Python standard library and require no credentials, GPU, network access, or model downloads. Dependencies are pinned to the versions used for verification; a clean environment avoids conflicts with existing A7 environments.

## Files and paths

- `data/cozyday_knowledge_base.json`: 30 paragraphs, IDs `P001`–`P030`; each record has nonempty string fields `id`, `title`, `topic`, and `body`.
- `chunking.py`: loading, chunking, and validation functions.
- `test_stage1.py`: 26 regression tests, including negative and boundary cases.
- `rag_system.ipynb`: Stage 1 demonstration, complete examples, validation, and saved outputs.
- `rag_analysis.md`: boundaries, semantic section mapping, counts, and limitations.
- `requirements.txt`: notebook dependencies only.

The default data path is derived from `chunking.py`'s location. A caller-provided relative data path is resolved against the caller's working directory. Run the examples below from `a8_rag/`; no machine-specific path is required. The notebook executes with `a8_rag/` as its working directory, including when invoked via nbconvert from the repository root.

The final team ZIP should put the required notebook, README, analysis, requirements, module, tests, and `data/` at its root. Later stages can add `results/` and their own modules inside `a8_rag/` without altering A7 files. Do not replace the repository's existing root README or requirements with these Stage 1 files.

## Frozen Stage 2 interface

```python
from chunking import load_knowledge_base, validate_knowledge_base, build_all_chunks
from chunking import fixed_length_chunks, overlapping_paragraph_chunks, hybrid_topic_chunks

records = load_knowledge_base()
summary = validate_knowledge_base(records)
chunks_by_strategy = build_all_chunks(records)

fixed = fixed_length_chunks(records, target_words=130)
overlap = overlapping_paragraph_chunks(records, window=2, stride=1)
hybrid = hybrid_topic_chunks(records, max_words=230)
texts = [chunk['text'] for chunk in chunks_by_strategy['fixed']]
# Stage 2 can pass texts to SentenceTransformer.encode and retain chunk metadata.
```

`build_all_chunks` always returns the keys `fixed`, `overlap`, and `hybrid`. Each value is a nonempty ordered list of these objects:

```json
{"chunk_id":"FIXED_001","strategy":"fixed","source_ids":["P001"],"topic":"Task Creation","text":"Complete chunk text...","word_count":112}
```

- `chunk_id`: strategy prefix plus a sequential number, e.g. `FIXED_001`, `OVERLAP_001`, `HYBRID_001`; IDs are unique across all three strategies.
- `source_ids`: ordered original paragraph IDs that actually contributed text. Fixed chunks may contain only some sentences from a paragraph; overlap and hybrid retain whole paragraphs.
- `topic`: the fine topic for fixed/hybrid and single-topic overlap windows. A mixed-fine-topic overlap window uses its explicitly documented related section label.
- `text`: the embedding input, with complete sentences and no display truncation.
- `word_count`: whitespace-separated text tokens only, excluding titles/IDs.

Functions are deterministic for the same ordered records and parameters. This correction changes earlier chunk boundaries and IDs; discard any chunks from the pre-review version. Freeze this corrected dataset, section mapping, ordering, and default parameters before Stage 2 indexes it. Custom parameter runs may reuse sequential IDs, so Stage 2 must store those in separate configuration-specific collections.

`validate_knowledge_base(records)` enforces the full assignment size limits. For the later scaling experiment, call `build_all_chunks(records[:10])` directly: chunkers and `validate_chunks` accept any nonempty valid subset, including one paragraph. Empty inputs and malformed records raise `ValueError`. Validation remains active with `python -O`.

## Boundary contract

- **Fixed, 30 chunks:** greedy whole-sentence packing to 130 words; always flush at a fine-topic change. A single overlong sentence remains whole; topic-boundary chunks can be shorter.
- **Overlap, 19 chunks:** whole adjacent paragraph windows, normally size two and stride one, inside related semantic sections only. `P001+P002`, `P002+P003`, `P003+P004` demonstrate actual overlap. A short section is emitted once; unrelated sections are never bridged.
- **Hybrid, 15 chunks:** nonoverlapping whole-paragraph groups with exactly the same fine topic and a 230-word soft cap. An oversized single paragraph stays whole.

For overlap, use positive integer parameters, with `stride < window` when `window > 1`; `window=1` only accepts `stride=1` and deliberately disables overlap for that custom run. A final end-anchored window covers any remaining tail without dropping paragraphs. Full semantic rules and their rationale are in `rag_analysis.md`.

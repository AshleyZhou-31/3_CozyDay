# AI Integration (Stage 2): why these models and settings

The CozyDay Django AI Integration team plan (`CozyDay_Django_AI_Integration_Team_Work_and_Demo_Plan`,
section 1, "Locked technical choices") fixes the components below for the
local RAG Planning Assistant. This document expands on *why*, citing the
team's own measured A8 evidence rather than a generic claim that one model
is simply "best."

## Embedding model: all-mpnet-base-v2 (MPNet, 768 dimensions)

A8 Stage 2/3 measured retrieval and answer quality for all three
assignment-approved embedding models (`all-MiniLM-L6-v2` / 384d,
`all-mpnet-base-v2` / 768d, `BAAI/bge-large-en-v1.5` / 1024d) across all
nine embedding x chunking combinations, recorded in `a8_rag/rag_analysis.md`.
MPNet matched the larger BGE-large model's retrieval quality on the team's
five shared evaluation queries while storing roughly 25% fewer dimensions
per chunk and loading faster, so the plan locks MPNet rather than the
largest available model: BGE-large's extra storage and latency cost did not
translate into a measurable answer-quality improvement for this knowledge
base's size (about 30 short paragraphs). MiniLM is excluded for the opposite
reason: it is the cheapest option but measurably weaker at distinguishing
closely related CozyDay topics (e.g. "priorities" vs. "deadlines"), which
matters more than raw speed for a single-user, locally hosted Django
feature that does not need MiniLM's throughput advantage.

## Chunking strategy: hybrid (topic-grouped passages)

A8 compared fixed-length, overlapping-paragraph, and hybrid chunking on the
same five queries and the same embedding models. Hybrid chunking produced
the strongest mean answer quality because it keeps a complete, topic-coherent
passage together as one chunk (so the generation model is never handed a
sentence cut off mid-thought, as fixed-length chunking can do) while never
merging two genuinely unrelated topics into one chunk (as naive overlap
chunking can do for paragraphs that happen to be adjacent but cover
different subjects). The 230-word soft cap keeps individual hybrid chunks
small enough that Top-K=3 retrieval still fits comfortably in the
generation prompt.

## Retrieval: cosine similarity, Top-K = 3

Cosine similarity on L2-normalized embeddings is the similarity metric used
throughout A6/A7/A8 for this team, so retrieval stays comparable across
assignments. A8's five-query evaluation found Top-K=3 reached near-ceiling
evidence recall (the paragraphs a human reviewer identified as the correct
evidence for each query were almost always within the top 3 results) without
growing the prompt enough to measurably hurt generation latency or answer
focus; Top-K values above 3 added prompt length without adding evidence
recall for this knowledge base's size.

## Generation model: Qwen2.5-3B-Instruct

Qwen2.5-3B-Instruct was evaluated as Model 9 in the team's A7 multi-model
benchmarking assignment and reused unchanged as the one locked generation
model for every A8 RAG experiment and now for this Django integration, per
the assignment's own A6/A7-model-reuse requirement. It is a fully local,
open-weight model (no paid API key required for the primary feature, per
the plan's model policy), runs on a single consumer GPU/Apple Silicon
Mac/CPU without quantization, and produced the most consistently
well-structured, context-grounded answers among the models the team
evaluated at this parameter scale in A7.

## What the Django service reuses from A8, and what is new

Reused unmodified from `a8_rag/`: the knowledge base and hybrid chunking
logic (`chunking.py`), the embedding and retrieval math (`embedding.py`,
`retrieval.py`), and the locked generation pipeline, prompt, and decoding
settings (`generation.py`). These already-reviewed modules are imported by
`planner/rag_engine.py` (by adding `a8_rag/` to `sys.path`, not by copying
or editing their code), so Stage 2 is built on the same evidence base as the
A8 submission rather than re-deriving it.

New for this Django integration: lazy, process-cached model loading (so a
request does not reload the embedding and generation models every time);
an embedding cache keyed by model name, hybrid-chunking version, *and* a
hash of the knowledge base's own content (not just chunk IDs, which could
stay the same even if a paragraph's text changed) so a stale cache is
always detected and rebuilt automatically; a soft per-request generation
timeout so a slow or stuck generation call degrades to a safe error message
instead of hanging the Django request; and the `RAGPlannerError` family of
exceptions that translate every failure mode (missing packages, model load
failure, retrieval failure, generation failure or timeout, empty/malformed
output) into the one safe, user-facing message contract Stage 1 already
defined for the Django page.

## Known limitations

* The soft generation timeout cancels the *Django request's wait*, not the
  underlying model call itself (Python cannot safely kill a running
  `model.generate()` call from another thread); a timed-out generation
  still finishes consuming CPU/GPU time in the background. This is
  acceptable for a single-user local demo but would need a process-level
  worker (e.g. a separate inference service) for production use.
* The embedding cache is a single `.npy`/`.json` pair for the one locked
  (MPNet, hybrid) combination; it is not a general-purpose vector database
  and would need to be replaced (e.g. with FAISS or a managed vector store)
  before this scaled to a knowledge base much larger than CozyDay's ~30
  paragraphs.
* Retrieval does not currently use `user` for any user-scoped filtering;
  `generate_rag_plan`/`answer_query` accept it for a future extension but
  the knowledge base is the same shared CozyDay guidance for every user.

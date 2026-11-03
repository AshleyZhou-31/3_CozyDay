# Team 3 CozyDay — P1 A8 Semantic Relationships and Retrieval

This folder is the complete submission source for CozyDay's Retrieval-Augmented Generation system. It implements the full path **data -> chunking -> embeddings -> retrieval -> Qwen generation -> output**, evaluates all nine embedding/chunking configurations, analyzes failures, and documents a production design for 10,000 users per day.

## Submission contents

- `rag_system.ipynb` — end-to-end implementation, saved experiment tables, failure examples, improvement comparison, cost reflection, and architecture.
- `rag_analysis.md` — full written analysis for Parts 1–4.
- `requirements.txt` — pinned Python dependencies.
- `data/cozyday_knowledge_base.json` — 30 paragraphs and 3,111 body words.
- `results/` — cached embedding arrays plus all row-level and summary experiment results.
- `system_architecture.svg` — scalable RAG design diagram.
- `chunking.py`, `embedding.py`, `retrieval.py`, `generation.py`, `rag.py` — pipeline modules.
- `queries.py`, `experiments.py`, `scoring.py` — frozen questions, experiment runner, and deterministic rubric.
- `test_stage1.py` through `test_stage4.py` — validation and integration tests.

The final archive is named `Team3-CozyDay-P1-A8.zip`. Its required files are at the ZIP root; no repository history, virtual environment, credentials, cache directory, or model weights are included.

## Experimental contract

- Embedding models: MiniLM 384 dimensions, MPNet 768, and BGE-large 1024.
- Chunking: fixed length, overlapping paragraphs, and hybrid same-topic groups.
- Generation: `Qwen/Qwen2.5-3B-Instruct`, greedy decoding, `max_new_tokens=300`.
- Retrieval: normalized cosine similarity, Top-K 3.
- Queries: the same five realistic questions in `queries.py` for all configurations.
- Main grid: 3 models x 3 strategies x 5 queries = 45 evaluations. Every row contains the retrieved chunks and generated answer.

Stage 4 does not alter the saved experimental results. It adds cost awareness, the RAG/fine-tuning/prompting comparison, the 10K-user architecture, final consistency checks, and submission packaging.

## Quick review without model downloads

Use Python 3.11 or newer. From the ZIP root (or from `a8_rag/` in the repository):

```bash
python -m unittest -v test_stage1.py
python -m unittest -v test_stage2.py
python -m unittest -v test_stage3.py
python -m unittest -v test_stage4.py
```

These tests validate the knowledge base, chunk boundaries, retrieval/generation interfaces, committed experiment tables, Stage 4 requirements, notebook integrity, and portability. Stage 2 includes one live MiniLM load/encode check and therefore downloads the smallest embedding model on its first run; it does not load the medium, large, or 3B generation model. Stages 1, 3, and 4 use saved data or stand-ins and require no model download.

Open `rag_system.ipynb` to inspect the saved outputs and all 45 evaluations. The Stage 3 notebook sections read the committed CSV files, so the results are available even on a machine without enough memory for model inference.

## Full clean-environment reproduction

Create an isolated environment and install the pinned dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

Then execute the canonical notebook from its own directory:

```bash
jupyter nbconvert --to notebook --execute rag_system.ipynb \
  --output rag_system_verified.ipynb \
  --ExecutePreprocessor.timeout=-1
```

The first full run downloads three sentence-transformer models and `Qwen/Qwen2.5-3B-Instruct`. Generation needs approximately 12 GB of free memory and can take substantial time on CPU. `rag_system_verified.ipynb` is a temporary verification copy and must not be placed in the final ZIP.

To reproduce Stage 3 row-level results separately, run:

```bash
python experiments.py main
python experiments.py scaling-retrieval
python experiments.py scaling-generation --model large --strategy hybrid
python experiments.py improve-prompt
python experiments.py improve-prompt --variant complete-within-limit
python experiments.py summary
```

Completed run IDs are skipped, so the commands resume safely. To perform a completely new experiment, use a copy of the folder and remove only the copied result files you intend to regenerate.

## Data and path behavior

All default paths are derived from module locations and are relative to this folder. No machine-specific path, token, password, API key, or external service is required. Model downloads use the standard Hugging Face cache outside the project and are not included in the ZIP.

The knowledge base contains general student-planning guidance, not live user data. Each paragraph has an ID, title, fine topic, and 80–200-word body. The chunk records retain complete text, source paragraph IDs, strategy, topic, and word count for retrieval diagnostics.

## Recommended production configuration

For this corpus, the recommended starting configuration is MPNet (768 dimensions), hybrid chunking (230-word soft cap), and Top-K 3. MPNet matched BGE-large on retrieval while using fewer vector dimensions; hybrid produced the best mean answer score. Production monitoring should evaluate broader held-out queries before treating this as a permanent choice.

The scalable design is in `system_architecture.svg` and the Stage 4 section of `rag_analysis.md`. It separates background ingestion/indexing from the online request path and includes tenant filtering, access control, caching, rate limiting, logging, monitoring, and horizontal generation workers.

## Build the final ZIP

From the repository root:

```bash
cd a8_rag
zip -r ../Team3-CozyDay-P1-A8.zip . \
  -x '*.git*' '*/.venv/*' '*/venv/*' '*/__pycache__/*' \
     '*/.ipynb_checkpoints/*' '*rag_system_verified.ipynb' \
     '*.pt' '*.bin' '*.safetensors' '*.gguf' '.env' '*.env'
```

Run `python test_stage4.py` after creating the ZIP; the final test also inspects its root files and exclusions.

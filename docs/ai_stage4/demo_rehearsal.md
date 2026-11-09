# A9 In-Person Demonstration Rehearsal

Scheduled slot: **Thursday, November 12, 2026, 11:15 AM — EDUC 338**  
Target length: 6 minutes, with the first request warmed before the instructor arrives.

## Before leaving for the room

1. Pull `main`, activate the environment and run `python manage.py check`.
2. Start the server and log into a non-personal demo account.
3. Open `/planitems/ai-rag-planner/` and submit Q1 once to load both models.
4. Keep these tabs ready: RAG Planner, this architecture document, Stage 3 final CSV,
   and the X1 before/after screenshots.
5. Keep the screenshots available as backup if model generation is slow or unavailable.
6. Hide notifications and close tabs containing email, tokens or personal information.

## Exact live sequence and speaking roles

### 0:00–0:45 — Ashley: goal and architecture

Show the repository and architecture diagram.

> CozyDay now integrates our earlier RAG work into an authenticated Django user flow.
> A question is validated, embedded with MPNet, matched against hybrid knowledge-base
> chunks by cosine similarity, and the top three chunks ground Qwen2.5-3B. The page then
> validates and displays the answer, sources, relevance scores and latency.

### 0:45–1:30 — Lin: Django input flow

Show login protection, the form, empty input and excessive input validation, then submit:

> I have a big semester paper due in a few weeks. How should I break it down into tasks in CozyDay?

Point out the answer, sources, scores, warning and timing.

### 1:30–3:15 — Rishabh: retrieval and generation

Show the Stage 2 service code and explain lazy model loading, the content-hash embedding
cache, MPNet + hybrid chunks + Top-K 3, Qwen2.5-3B, safe exceptions, and the soft-timeout
limitation. Submit or reveal the warmed result for:

> How do I build a weekly study plan and prepare for my exam using spaced review?

### 3:15–5:15 — Shivani: measured evaluation and failure

Show `stage3_results_final.csv`, then submit:

> What is the capital of France and who designed the Eiffel Tower?

Explain that the best relevance score is about 0.04, generation is skipped, and the page
refuses instead of answering from general knowledge. Show the before screenshot where the
old system answered “Paris” and the after screenshot. Also mention Q1 truncation and output
validation.

### 5:15–6:00 — Ashley: reproducibility, limitations and closing

> The full setup, model downloads, automated tests, real-model smoke test and evidence paths
> are documented in the README. The system keeps secrets in environment variables and does
> not retrieve private user data. Its main limitations are the first-run download, local CPU
> latency, a soft rather than hard timeout, a static shared corpus and a small NumPy vector
> cache. For production we would separate inference into a queued worker and use a persistent
> vector store with per-user access controls. The final implementation and evidence are on main.

## Likely questions

- **Why MPNet instead of the largest embedding?** It matched BGE-large on the A8 team
  queries with 25% fewer dimensions; MiniLM was faster but weaker on nearby topics.
- **Why Top-K 3?** It captured the expected evidence without adding lower-ranked noise.
- **How is hallucination reduced?** Retrieved context grounds the prompt and the 0.35
  relevance gate skips generation when retrieval is weak.
- **Does the system read users' tasks?** No. The current corpus is shared CozyDay guidance.
- **What is the biggest latency cost?** Local Qwen generation; embedding and retrieval were
  only hundredths of a second in the recorded run.
- **What if the model times out?** The user gets a safe message, but the background thread may
  still finish; production needs a separate killable worker process.

## Backup path

If live inference fails, show:

- `docs/ai_stage3_evaluation/screenshots/q1_success.png`
- `docs/ai_stage3_evaluation/screenshots/q3_success.png`
- `docs/ai_stage3_evaluation/screenshots/x1_before_gate_off.png`
- `docs/ai_stage3_evaluation/screenshots/x1_after_gate_on.png`
- `docs/ai_stage3_evaluation/stage3_results_final.csv`

State clearly that these are committed outputs from the same integrated Django route.

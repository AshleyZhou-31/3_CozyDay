# CozyDay AI Planner (Stage 3: local Hugging Face model)

The **AI Planner** page (`/planitems/ai-planner/`, link in the navigation bar once logged in) turns a short
free-text request such as *"I have a 2 PM meeting, an assignment due at 5 PM that needs 2 hours, and a
30-minute workout"* into a **Priority / Schedule / Reason** suggestion. The model runs on your own computer
through Hugging Face Transformers; no API key is needed.

## Selected model

`Qwen/Qwen2.5-3B-Instruct` with few-shot prompting (3 examples). Evidence and the full 15-model comparison are in
`llm-test/ai_prototype.ipynb` (Stage 3 results section) and `llm-test/results/model_*_results.csv`.
The model uses the Qwen Research License (see its model card); this is fine for coursework.

## Run it locally

```bash
git switch ai-3-local-llm-integration      # or the merged main branch
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # installs torch + transformers (large download)
cp .env.example .env                       # set DJANGO_SECRET_KEY
python manage.py migrate
python manage.py runserver
```

1. Log in (or sign up), open **AI Planner**, type a request, press **Suggest a plan**.
2. The **first** request downloads the model (about 6 GB, cached in `~/.cache/huggingface`) and loads it, which can
   take several minutes. Later requests reuse the loaded model; expect roughly 10-60 seconds each on CPU, faster on
   a GPU or Apple silicon.
3. Needs roughly 8 GB of free RAM (the model loads in bfloat16 on CPU, float16 on GPU/MPS).

Optional environment variables (all have defaults): `AI_PLANNER_MODEL_ID`, `AI_PLANNER_DEVICE`
(`auto`/`cpu`/`cuda`/`mps`), `AI_PLANNER_MAX_INPUT_CHARS` (600), `AI_PLANNER_MAX_NEW_TOKENS` (256),
`AI_PLANNER_MAX_TIME_SECONDS` (120), `AI_PLANNER_MAX_PLAN_ITEMS` (10), `AI_PLANNER_FEW_SHOTS` (3).

## Data input, preprocessing and guardrails

* **Input:** one text box, plus an optional checkbox that adds the titles of the user's own open plan items
  (never other users' items, never notes).
* **Preprocessing:** control and zero-width characters removed, all whitespace collapsed, empty input rejected,
  input over 600 characters rejected (not silently cut), plan-item titles trimmed to 80 characters and limited to 10.
* **Prompt:** the same system instruction and few-shot examples that were evaluated in the notebook.
* **Output handling:** the response must contain `Priority:` and `Schedule:`; a missing `Reason:` or a cut-off
  reply is shown with a notice. Empty or unstructured output shows an error message instead of a plan.
* **Failures:** missing packages, download/memory errors, generation errors and timeouts (`max_time`) never crash
  the page; the user sees a short message and the details go to the server log.
* Page is login-protected, uses CSRF protection, and all model text is HTML-escaped by Django templates.

## Tests

`python manage.py test` (the AI tests are in `planner/test_ai_planner.py`). They mock torch, transformers and
generation, so nothing is downloaded and the suite stays fast.

## Known limitations

* The 3B model sometimes double-books fixed times (for example the 1-3 PM class in test T3); treat suggestions as a
  starting point.
* Single-process model cache: each server process loads its own copy of the model.
* Not suitable for hosts with small disk/RAM quotas (for example the PythonAnywhere free tier); there the page
  reports that the local model is unavailable.

# CozyDay AI Features

CozyDay now offers two planning assistants:

1. **Local AI Planner** (`/planitems/ai-planner/`) uses
   `Qwen/Qwen2.5-3B-Instruct` through Hugging Face Transformers. Model weights
   and inference remain on the application host.
2. **API Planner** (`/planitems/api-ai-planner/`) uses Google's Gemini API
   (`gemini-2.5-flash-lite` by default). It demonstrates a second AI feature
   with a different deployment and cost model.

Both features require login, use the same validated form, and return a
Priority / Schedule / Reason structure. AI output is advisory and is never
saved automatically as a PlanItem.

## Setup

Follow the normal project setup in `README.md`. For the local planner, the
default model downloads on first use. It can be changed in `.env`:

```text
AI_PLANNER_MODEL_ID=Qwen/Qwen2.5-3B-Instruct
```

For the external API planner, create a Gemini API key and add it only to the
untracked `.env` file:

```text
GEMINI_API_KEY=<your real key>
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_API_TIMEOUT_SECONDS=20
```

Never commit a real key. `.env.example` contains placeholders only. The Gemini
implementation follows Google's `generateContent` REST pattern and sends the
key in the `x-goog-api-key` header, not in the URL.

## Data Input

The main input is free text entered by an authenticated user, such as "I need
to finish a report and buy groceries tonight." The optional checkbox permits
the system to add that same user's incomplete PlanItem titles. The query is
always filtered by `request.user`; another user's records cannot enter the
prompt. The feature does not send account IDs, usernames, email addresses,
categories, dates, or PlanItem notes.

The 15-model evaluation uses six fixed scenarios and the same output contract.
The evidence is in `llm-test/results/`, and the reproducible notebook is
`llm-test/ai_prototype.ipynb`.

## Preprocessing

Before either AI path runs, `clean_user_text()`:

- removes control and invisible characters;
- collapses repeated whitespace;
- rejects empty input;
- rejects input over 600 characters instead of silently truncating it.

Optional PlanItem titles are cleaned again, limited to 80 characters each,
and capped at 10 titles. The local model uses the tested system instruction
and three few-shot examples. The Gemini request uses the same system
instruction and a low temperature (`0.2`) for stable formatting. Both outputs
are parsed into a `PlannerResult`, and output without usable Priority and
Schedule sections is rejected.

## Safety Guardrails and Workflow

The workflow is:

1. Require authentication and CSRF protection.
2. Validate and normalize user input.
3. Fetch only the authenticated user's open titles, and only after explicit
   checkbox consent.
4. Apply the system instruction: use only supplied information, do not invent
   deadlines, and return concise planning advice.
5. Run local inference or call Gemini with a timeout.
6. Validate the response structure.
7. Render with Django auto-escaping; never mark model output as safe HTML.
8. Show a non-technical error for missing configuration, timeout, quota,
   provider failure, blocked content, invalid JSON, or malformed output.

Additional protections:

- API credentials are environment variables and are not logged or returned.
- The Gemini key is placed in an HTTP header.
- Raw provider error bodies and private prompt text are not logged.
- API output is not trusted as HTML and cannot execute scripts in the page.
- The service has a 20-second default network timeout.
- AI suggestions do not modify the database without a separate future user
  confirmation workflow.
- The page warns users that selected text is sent to Google and asks them not
  to enter sensitive personal information.

Known limitations: model suggestions may be inaccurate, incomplete, or
overconfident. Users must verify dates and priorities. The external feature
also depends on provider availability, quota, pricing, and data-processing
terms.

## Testing

The test suite does not download a local model or call Google. Local inference
uses small fakes, and Gemini HTTP responses are mocked. Tests cover:

- authentication and CSRF-backed page flow;
- input cleaning and length limits;
- per-user PlanItem isolation;
- opt-in data inclusion;
- API key header, payload, model URL, and timeout;
- timeout, connection, credential, quota, safety-block, invalid JSON, and
  malformed-output behavior;
- HTML escaping of untrusted model output.

Run:

```bash
python manage.py test
python manage.py check
```

## Sources

- Google, "Text generation," Gemini API documentation:
  https://ai.google.dev/gemini-api/docs/text-generation/ (accessed 2026-10-19)
- Google, "Gemini Developer API pricing":
  https://ai.google.dev/gemini-api/docs/pricing (accessed 2026-10-19)
- Hugging Face model cards linked in
  `llm-test/results/research_matrix.csv` (accessed during the model study).


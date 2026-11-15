# A10 Stage 3: cost, monitoring, simulation and responsive design

Branch: `a10-stage3-cost-monitoring-shivani`. This package covers cost and
token tracking, the cost widgets on the System metrics page, a repeatable
simulated-data command, optional Sentry monitoring and responsive
typography and spacing. It builds on Lin's logging foundation
(`AIPerformanceEvent`), Rishabh's categories and dashboard, and the feedback,
relevance and template-comparison work merged in PR #39.

## What was added

| Area | Where |
| --- | --- |
| Token and cost estimation | `planner/ai_cost.py`, wired in `planner/rag_engine.py` and `planner/views.py` |
| New fields `model_name`, `serving_backend` | `planner/models.py`, migration `0007_aiperformanceevent_model_backend` (depends on `0006_airesponsefeedback` from PR #39) |
| Cost and token widgets | `planner/cost_dashboard.py`, `planner/templates/planner/system_analytics.html`, `system_analytics.css` |
| Simulated data command | `planner/management/commands/seed_ai_analytics.py` |
| Optional Sentry | `cozyday/monitoring.py`, hook at the end of the AI settings in `cozyday/settings/base.py` |
| Responsive typography and spacing | `planner/static/planner/style.css`, `system_analytics.css` |
| Tests | `test_a10_stage3_cost.py`, `test_a10_stage3_dashboard.py`, `test_a10_stage3_seed.py`, `test_a10_stage3_monitoring.py` |

## How cost is estimated

The model runs on CozyDay's own hardware, so there is no per-request bill.
The **primary** cost metric is local compute:

```
estimated cost = generation_seconds / 3600 x AI_HARDWARE_RATE_USD_PER_HOUR
```

`AI_HARDWARE_RATE_USD_PER_HOUR` is configurable and defaults to `0.50`
(USD per hour). The cost is stored in `AIPerformanceEvent.estimated_cost_usd`.
A request refused by the relevance gate never calls the model, so it records
0 generation seconds, 0 tokens and $0.

**Token counts are a separate usage metric**, shown beside the cost. They use
the loaded Qwen tokenizer when it is available and fall back to one token
per four characters otherwise. Input tokens are the template instruction, the
retrieved chunks and the question; output tokens are the raw generated answer.
Chat-format special tokens are not counted, so input is slightly understated.

A **secondary, API-equivalent** estimate is also shown, clearly labelled. It
is tokens x an assumed hosted-API price (`AI_COST_INPUT_USD_PER_1K=0.0002`,
`AI_COST_OUTPUT_USD_PER_1K=0.0004`) and answers "what might the same usage
cost on a hosted API?". It is **not** the actual cost of the local model. It
is calculated from the stored token counts when the page loads, so it needs no
extra database column. Every dollar figure on the page says "estimated".

## What is stored, and what is not

Stored per request: outcome, timings, relevance score, query category, query
length in characters, estimated input and output tokens, estimated cost,
model name and serving backend. (Estimated cost is the local-compute figure.) No question, answer, retrieved text or user
ID is stored. Tests assert this.

## Dashboard widgets (System metrics page, staff only)

- Total estimated cost and mean cost per request (local compute; refusals count as $0), total tokens, mean generation time, and the secondary API-equivalent estimate
- Estimated cost by topic and token usage by topic (bars)
- Cost vs. generation time by topic (table, with the API-equivalent column marked secondary)
- Serving backend comparison: backend, model, requests, mean latency, mean generation time, mean cost

All widgets are computed from database rows on each page load. **The page
shows real records by default.** Simulated records are included only with the
explicit option `?simulated=1`, which also shows a visible "Simulated data
included" notice at the top of the page. When simulated records exist but are
hidden, a note says how many and links to `?simulated=1`. This applies to the
feedback distribution, weighted score and template widgets from PR #39 as well.

## Simulated data

```
python manage.py seed_ai_analytics            # replace simulated rows with 100 new ones
python manage.py seed_ai_analytics --count 60
python manage.py seed_ai_analytics --clear    # remove simulated rows only
```

- Every record has `is_simulated=True`. Real records are never created, changed or deleted.
- About 55% of successful simulated answers also get a deterministic feedback rating (about 60% accurate, 28% partially accurate, 12% not accurate), so the feedback distribution, weighted accuracy and template-comparison widgets contain demonstration data. Ratings are attached to simulated events only and are removed with them; real feedback is never touched.
- Simulated cost uses the primary metric: each record's generation time at the hourly hardware rate.
- Each run first removes the previous simulated records and then creates exactly `--count` (1 to 500), so reruns cannot accumulate duplicates. Output is deterministic for a given `--seed`.
- Values are illustrative, not measurements. Timings and relevance scores stay inside the verified A9 ranges (generation 3 to 21 s, in-scope best relevance 0.527 to 0.762, out-of-scope 0.02 to 0.18). Input tokens follow the first real requests (about 890 each). About 80% of records succeed, 15% abstain and 5% error.
- All simulated requests use the `transformers-local` backend because no other backend has been measured, so the backend comparison does not invent results.

## Optional Sentry

Off unless `SENTRY_DSN` is set. Without a DSN, or without `sentry-sdk`
installed, the app runs normally. When enabled, events are scrubbed before
sending: request bodies, cookies, headers, query strings, user details, local
variables and exception messages are removed; only the exception type, code
location, and request method and path remain. Variables: `SENTRY_DSN`,
`SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` (default 0).

Verification: unit tests cover the on, off, missing-package and failure paths
and the scrubbing; the settings were also accepted by the real `sentry-sdk`
2.x. No event was sent to a live Sentry project, so delivery is not tested.

## Responsive typography and spacing

Headings, body text, page gutters and card padding now use `rem` and
`clamp()`. Summary cards use `auto-fit` grids so numbers no longer wrap. On
phones, the 14-day chart shows every third date and wide tables scroll inside
their panel.

Checked in headless Chromium with sample data on six pages (home, plan items,
System metrics, RAG Planner, analytics, reports) at 320, 390, 768, 1000, 1100
and 1440 px wide. Before the change, System metrics scrolled sideways on
phones (+194 px at 320, +124 px at 390); afterwards none of the pages scroll
sideways at any of these widths. The navigation bar scrolls horizontally on
phones by design.

## Setup

```
cp .env.example .env            # optional; all new settings have defaults
python manage.py migrate
python manage.py seed_ai_analytics
python manage.py runserver
```

Open `/planitems/system-analytics/` for real records, or add `?simulated=1` to
see the demonstration data.

Log in as a staff user and open System metrics. To use real data, submit
questions on the RAG Planner page. `sentry-sdk` is in `requirements.txt` but
only needed when `SENTRY_DSN` is set.

## Evidence

Real requests on a laptop (2 answered, 1 refused), measured before the cost
basis changed: the two answers used 1,778 input and 346 output tokens in total
(about 889 and 173 each) with a mean generation time of 13.4 s. At the default
$0.50/hour that is about $0.00186 per answered request (13.4 / 3600 x 0.50);
the secondary API-equivalent estimate for the same requests was about
$0.000247 each. The refusal recorded 0 tokens and $0.

| Screenshot | Shows |
| --- | --- |
| `screenshots/cost_dashboard_real_only.png` | 1440 px, default view: real requests only, simulated-hidden note |
| `screenshots/cost_dashboard_desktop.png` | 1440 px with `?simulated=1`: "Simulated data included" notice |
| `screenshots/feedback_widgets_simulated.png` | `?simulated=1`: feedback distribution, weighted score and template performance with seeded ratings |
| `screenshots/cost_dashboard_phone.png` | 390 px, no sideways scrolling |
| `screenshots/rag_planner_phone.png` | RAG Planner at 390 px, answer and sources readable, no sideways scrolling |
| `screenshots/seed_command_output.png` | Output of `seed_ai_analytics`, including the feedback ratings |

## Limitations

- Costs are estimates. The local-compute figure depends on the assumed $0.50/hour hardware rate, and the API-equivalent figure on assumed token prices; neither is an invoice.
- Token counts omit chat-format overhead, and the fallback is a rough approximation.
- Mean cost per request includes refusals at $0.
- Local-compute cost is proportional to generation time by construction, so "cost vs. generation time" shows the same trend; the API-equivalent column follows token counts.
- Simulated data is illustrative; only one backend has real measurements.
- Sentry delivery is untested against a live project.
- On phones, wide tables need a sideways swipe inside their panel.

## Handoff note for Ashley

- Migration `0007` adds `model_name` and `serving_backend` to `AIPerformanceEvent` and depends on `0006_airesponsefeedback` (PR #39). PR #39's feedback, relevance-score, template-comparison and event-return behaviour is preserved.
- Primary cost is local compute (`generation_seconds / 3600 x AI_HARDWARE_RATE_USD_PER_HOUR`, default $0.50/hour). Tokens are a separate usage metric; the token-price figure is a secondary, API-equivalent estimate.
- The dashboard shows real records by default; simulated records need `?simulated=1` and show a notice. Run `python manage.py seed_ai_analytics` once on the production demo database; rerunning is safe.
- `requirements.txt` gains `sentry-sdk>=2.0,<3` (optional).
- `db.sqlite3` is tracked in this repository; do not commit local changes to it.
- No model weights, credentials or real questions are committed.

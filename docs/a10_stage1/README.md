# A10 Stage 1 AI performance logging and dashboard

This package adds privacy-minimal performance logging for CozyDay's authenticated RAG Planner and a staff-only dashboard. It establishes the performance layer for the later user-behavior and cost analytics stages.

## What is measured

Each RAG Planner POST records its timestamp, outcome (`success`, `abstention`, or `error`), total server-side pipeline time, embedding/retrieval/generation stage times when returned by the RAG service, Django response-schema validation time, maximum retrieval similarity, and number of retrieved chunks. Invalid submissions and service failures are counted as errors. Requests that stop at the relevance gate are counted as abstentions. Success rate is also shown as a dashboard KPI.

Records do not include user IDs, prompts, answers, retrieved passages, IP addresses, or account names. Nullable fields reserve privacy-safe space for later query-length/category, token/cost estimate, and simulation metadata. Stage 1 leaves the query and cost placeholders empty and marks live requests as non-simulated. Persistence is best-effort so an analytics database problem does not prevent a planning response from being returned. Request and stage times are measured in milliseconds; displayed latency statistics cover the latest 30 days.

## Dashboard access

- URL: `/planitems/system-analytics/`
- Requires login and `is_staff=True`.
- Shows success rate; mean, median, and interpolated P95 total latency; a 14-day mean-latency trend; mean time by pipeline stage; and success/abstention/error shares.
- The page reports an explicit empty state until genuine RAG requests have been recorded. Do not seed synthetic values into production for this Stage 1 package.
- Existing personal plan-item analytics at `/planitems/analytics/` remains unchanged.

## Setup and checks

```bash
python manage.py migrate
python manage.py check
python manage.py test planner.test_a10_stage1_analytics
```

Migration `0002_aiperformanceevent.py` creates the event table. Migration `0003_aiperformanceevent_estimated_cost_usd_and_more.py` adds nullable fields for query length/category, token and cost estimates, and simulated-record status. The existing RAG Planner form and service remain the source of truth for input validation and AI processing.

## Evidence

`screenshots/system_analytics_empty.png` shows the real empty-state dashboard rendered with a local staff account. It intentionally contains no synthetic analytics. The automated tests cover successful logging, validation-timer boundaries, abstention logging, error and invalid-input logging, privacy-safe placeholder fields, staff-only access, percentile calculations, and the empty state.

## Handoff to Stage 2

The shared event schema is ready for safe extensions. Stage 2 can populate query-category and length fields; Stage 3 can populate token/cost estimates and simulated demonstration records. Continue excluding raw prompt text, responses, and account identifiers. Later usage and cost visualizations can share the staff-only dashboard.

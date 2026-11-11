# A10 Stage 1 AI performance logging and dashboard

This package adds privacy-minimal performance logging for CozyDay's authenticated RAG Planner and a staff-only dashboard. It establishes the performance layer for the later user-behavior and cost analytics stages.

## What is measured

Each RAG Planner POST records its timestamp, outcome (`success`, `abstention`, or `error`), total server-side pipeline time, embedding/retrieval/generation stage times when returned by the RAG service, Django response-schema validation time, maximum retrieval similarity, and number of retrieved chunks. Invalid submissions and service failures are counted as errors. Requests that stop at the relevance gate are counted as abstentions.

Records do not include user IDs, prompts, answers, retrieved passages, IP addresses, or account names. Persistence is best-effort so an analytics database problem does not prevent a planning response from being returned. Request and stage times are measured in milliseconds; displayed latency statistics cover the latest 30 days.

## Dashboard access

- URL: `/planitems/system-analytics/`
- Requires login and `is_staff=True`.
- Shows mean, median, and interpolated P95 total latency; a 14-day mean-latency trend; mean time by pipeline stage; and success/abstention/error shares.
- The page reports an explicit empty state until genuine RAG requests have been recorded. Do not seed synthetic values into production for this Stage 1 package.
- Existing personal plan-item analytics at `/planitems/analytics/` remains unchanged.

## Setup and checks

```bash
python manage.py migrate
python manage.py check
python manage.py test planner.test_a10_stage1_analytics
```

The migration is `planner/migrations/0002_aiperformanceevent.py`. The existing RAG Planner form and service remain the source of truth for input validation and AI processing.

## Evidence

`screenshots/system_analytics_empty.png` shows the real empty-state dashboard rendered with a local staff account. It intentionally contains no synthetic analytics. The automated tests cover successful logging, abstention logging, error and invalid-input logging, privacy-sensitive schema exclusions, staff-only access, percentile calculations, and the empty state.

## Handoff to Stage 2

The new event table is ready for safe aggregate extensions. Stage 2 can add query categories and length bands through an explicit migration and should continue excluding raw prompt text and account identifiers. Its usage visualizations can share the staff-only dashboard after integration.

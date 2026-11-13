# A10 refinement — response feedback, relevance display, and widget expansion

This package extends the Stage 2 user-behavior analytics with user-facing feedback collection and relevance-score visibility, and adds four panels to the existing staff-only dashboard summarizing that new data alongside query-length distribution.

## What is added

`AIResponseFeedback` is a one-to-one accuracy rating (Accurate / Partially accurate / Not accurate) attached to a single `AIPerformanceEvent`. No prompt or answer text is stored here, only the derived rating. One event holds only one feedback record: resubmitting a rating via the same form updates the record in place through `update_or_create()` rather than creating a duplicate, since `AIPerformanceEvent` carries no user ID to use for ownership or idempotency checks.

`submit_ai_feedback` is a new view at `POST /planitems/ai-rag-planner/feedback/<event_id>/`, login required. It accepts one of the three rating values, rejects anything else with a user-facing message instead of a 500, and 404s on an unknown event id. It does not check that the submitting user "owns" the event, because there is nothing to check ownership against by design — see the view's docstring.

The RAG Planner result page now shows the best relevance score as a percentage, computed from the already-returned `retrieved_chunks` scores, and, when a response was successfully logged, a three-button feedback form beneath it. `django.contrib.messages` is now rendered on this template, scoped here rather than in `base.html`, to avoid interfering with Ashley's planned unified-UI pass.

## Dashboard additions

`/planitems/system-analytics/` gains four more panels: an accuracy-rate KPI card, a query-length distribution breakdown (five buckets plus "Unknown" for events predating this field), a feedback-rating distribution, and a template-performance comparison table (count, mean latency, and success/abstention/error split per template type, reusing Lin's `template_type` field). The accuracy-rate KPI and feedback distribution both read as empty/`None` correctly when no feedback has been submitted yet, rather than dividing by zero.

The dashboard's privacy statement has been updated to disclose that template type and an optional accuracy rating are now also stored, alongside the fields Stage 1 and Stage 2 already disclosed.

## Setup and checks

```bash
python manage.py makemigrations planner
python manage.py migrate
python manage.py check
python manage.py test planner
```

One new migration, `0006_airesponsefeedback.py`, creates the `AIResponseFeedback` table. No existing field's schema changes.

## Evidence

`screenshots/system_analytics_refinement.png` shows the dashboard after real feedback submissions. Automated tests in `planner.test_a10_refinement_feedback_relevance` cover: feedback creation, update-in-place on resubmission, rejection of an invalid rating without creating a row, the login requirement, 405 on GET, 404 on an unknown event id, relevance-score computation including the empty-retrieval edge case, and all four dashboard aggregations including their zero-data edge cases. Full suite: 207/207 passing.

## Handoff

The feedback form currently has no per-user ownership or rate-limiting: any authenticated user who knows a valid event id can rate it, and can re-rate it as many times as they like, overwriting their own prior rating each time. That is an accepted trade-off given `AIPerformanceEvent` has no user ID by design. If a later stage adds user attribution to events, this is the place to add an ownership check.

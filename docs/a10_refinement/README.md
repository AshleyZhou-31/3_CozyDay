# A10 refinement — response feedback, relevance display, and widget expansion

This package extends the Stage 2 user-behavior analytics with user-facing feedback collection and relevance-score visibility, and adds four panels to the existing staff-only dashboard summarizing that new data alongside query-length distribution. Updated after Ashley's review to close a feedback-integrity gap and to make the "accuracy" metrics reflect partial credit instead of only exact matches.

## What is added

`AIResponseFeedback` is a one-to-one accuracy rating (Accurate / Partially accurate / Not accurate) attached to a single `AIPerformanceEvent`. No prompt or answer text is stored here, only the derived rating. One event holds only one feedback record: resubmitting a rating via the same form updates the record in place through `update_or_create()` rather than creating a duplicate.

`submit_ai_feedback` is a view at `POST /planitems/ai-rag-planner/feedback/<event_id>/`, login required, that accepts one of the three rating values, rejects anything else with a user-facing message instead of a 500, and 404s on an unknown event id.

The RAG Planner result page shows the best relevance score as a percentage, computed from the already-returned `retrieved_chunks` scores, and, when a response was successfully logged (success or abstention — not a genuine error, since there is nothing to rate there), a three-button feedback form beneath it. `django.contrib.messages` is rendered on this template, scoped here rather than in `base.html`, to avoid interfering with Ashley's planned unified-UI pass.

## Feedback integrity: signed tokens, not just a login check

`AIPerformanceEvent` has no user ID by design (privacy-minimal logging), so the feedback endpoint cannot check account-level ownership. The first version of this feature treated "any authenticated user" as good enough, documenting the gap as an accepted trade-off. Ashley's review correctly flagged that this does not actually protect the analytics data: `AIPerformanceEvent` ids are sequential, so any logged-in user could increment through ids and overwrite other people's ratings.

The fix: the RAG Planner result page now embeds a signed, per-event token (`_make_feedback_token` / `_verify_feedback_token` in `planner/views.py`, built on `django.core.signing`) as a hidden field in the feedback form, generated at the same moment the event is recorded. `submit_ai_feedback` rejects the request with `403 Forbidden` unless the submitted token verifies against that exact event id. A token minted for one event cannot be reused, guessed, or incremented into rating a different event — the signature only validates for the id it was signed with — and no session or user identifier needs to be stored to enforce this. See `planner/test_a10_refinement_feedback_relevance.py::FeedbackSubmissionTests` for the tests confirming a missing token, a garbage token, and a token minted for a different event are all rejected without creating or changing a rating.

## Weighted accuracy, not accurate-only

The first version's "Accuracy rate" counted only exact "Accurate" ratings and scored "Partially accurate" the same as "Not accurate" (both zero). Ashley pointed out this doesn't actually measure answer quality — a template that gets consistently partial credit from users looks identical to one that's consistently wrong.

Both the dashboard's KPI card (now labeled "Weighted accuracy score") and the per-template comparison table use the same weighting: Accurate = 1.0, Partially accurate = 0.5, Not accurate = 0.0, averaged over rated responses and shown as a percentage (`_weighted_accuracy_percent` in `planner/views.py`). It reads `None`/`—` when nothing has been rated yet rather than dividing by zero. This is documented inline in the KPI card's caption and in the table's footer caption, not just in this file.

## Dashboard additions

`/planitems/system-analytics/` gains four more panels: a weighted accuracy-score KPI card, a query-length distribution breakdown (five buckets plus "Unknown" for events predating this field), a feedback-rating distribution, and a template-performance comparison table. The table now reports, per template type: request count, mean latency, success/abstention/error split, how many of that template's responses were rated, and that template's own weighted accuracy score — so a template's answer quality can be compared directly against another's, not just its completion rate.

The dashboard's privacy statement discloses that template type and an optional accuracy rating are now also stored, alongside the fields Stage 1 and Stage 2 already disclosed.

## Setup and checks

```bash
python manage.py makemigrations planner
python manage.py migrate
python manage.py check
python manage.py test planner
```

One migration, `0006_airesponsefeedback.py`, creates the `AIResponseFeedback` table. The signed-token fix added no new field or migration — the token is derived on the fly from the event id and the server's existing `SECRET_KEY`, nothing new is persisted.

## Evidence

`screenshots/system_analytics_refinement.png` shows the dashboard after real feedback submissions. Automated tests in `planner.test_a10_refinement_feedback_relevance` cover: feedback creation, update-in-place on resubmission, rejection of an invalid rating, the login requirement, 405 on GET, 404 on an unknown event id, rejection of a missing/garbage/wrong-event token, relevance-score computation including the empty-retrieval edge case, weighted-accuracy's partial-credit behavior (distinguished from the old accurate-only calculation with a dedicated test), and the template-performance table's per-template rated count and weighted score. Full suite: 212/212 passing.

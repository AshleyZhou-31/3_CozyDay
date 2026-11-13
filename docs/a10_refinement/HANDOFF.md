# Refinement handoff

Response feedback and relevance-score display are implemented and covered by `planner.test_a10_refinement_feedback_relevance`. Every successful or abstained RAG Planner response now shows its best retrieval relevance score and a three-button accuracy-feedback form; submitting feedback creates or updates a one-to-one `AIResponseFeedback` row without ever storing prompt or answer text.

Feedback submission is protected by a signed, per-event token embedded in the result page at the moment the event is logged — not just a login check — so a user cannot overwrite another event's rating by incrementing a sequential event id. See the README's "Feedback integrity" section for the full reasoning and `FeedbackSubmissionTests` for the tests proving it.

The dashboard at `/planitems/system-analytics/` adds a weighted accuracy-score KPI, a query-length distribution panel, a feedback-rating distribution panel, and a template-performance comparison table that reports each template's rated-response count and its own weighted accuracy score, not just its completion/error counts. "Weighted" means Accurate=1.0, Partially accurate=0.5, Not accurate=0.0 — see the README's "Weighted accuracy" section before changing those weights, since it would silently reclassify historical dashboard data.

Before merging, apply this package's one migration (`0006_airesponsefeedback.py`) and confirm all four new panels render against real data rather than the empty state.

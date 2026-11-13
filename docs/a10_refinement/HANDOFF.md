# Refinement handoff

Response feedback and relevance-score display are implemented and covered by `planner.test_a10_refinement_feedback_relevance`. Every successful RAG Planner response now shows its best retrieval relevance score and a three-button accuracy-feedback form; submitting feedback creates or updates a one-to-one `AIResponseFeedback` row without ever storing prompt or answer text.

The dashboard at `/planitems/system-analytics/` adds an accuracy-rate KPI, a query-length distribution panel, a feedback-rating distribution panel, and a template-performance comparison table, built with the same CSS patterns as the existing Stage 1/2 panels.

Before merging, apply this package's one new migration (`0006_airesponsefeedback.py`) and confirm the four new panels render against real data rather than the empty state — the screenshot documents a populated dashboard with real submitted feedback, not the zero-feedback state. The feedback form has no ownership check by design (see README); treat that as a known trade-off, not an oversight, if it comes up in review.

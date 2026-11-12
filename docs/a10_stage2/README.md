# A10 Stage 2 user-behavior analytics

This package extends Stage 1's privacy-minimal performance logging to populate the query-length and query-category fields it left reserved, and adds topic-level panels to the existing staff-only dashboard. It establishes the user-behavior layer for later cost and simulation-tracking stages.

## What is measured

On every successful RAG Planner submission, and on every submission that fails after the form itself validated, the view now computes `query_length_chars` (the character count of the cleaned query, capped at the field's 32767-character maximum) and `query_category` from that same cleaned query text, via a new `categorize_query()` function.

Category is chosen from a fixed, ordered list of six labels — Task breakdown, Prioritization, Study planning, Privacy & sharing, Progress reporting, and Other — using deterministic, case-insensitive keyword matching with a documented precedence order (the first category in the list whose keywords match wins; see `_QUERY_CATEGORY_KEYWORDS` in `planner/views.py`). Invalid form submissions never reach categorization and leave both fields `None`, matching Stage 1's existing error-handling path. The raw query text itself is never stored, logged, or passed to categorization before cleaning — only its derived length and category label.

## Dashboard additions

`/planitems/system-analytics/` (the same staff-only URL from Stage 1) now also shows three panels: a 14-day daily request-volume chart, a 30-day "Common topics" category breakdown, and a "Topic vs. outcome" table cross-referencing each category against its request count, average query length, and success/abstention/error split. An "Uncategorized" row covers events recorded before this stage, or from any future code path that does not supply a query.

These reuse Stage 1's existing reporting windows (30 days for summary and category data, 14 days for the daily trend) and its existing CSS bar-chart and list patterns rather than introducing a new chart library, consistent with the team's no-new-JS-framework agreement.

## Setup and checks

```bash
python manage.py migrate
python manage.py check
python manage.py test planner
```

No new migration is required. `query_length_chars` and `query_category` already existed as nullable fields from Stage 1's `0003_aiperformanceevent_estimated_cost_usd_and_more.py` migration, added specifically so a later stage could populate them without a schema change.

## Evidence

`screenshots/system_analytics_populated.png` shows the dashboard after real RAG Planner requests covering all five documented categories plus an off-topic case. Automated tests in `planner.test_a10_stage2_user_behavior` cover: correct assignment for every documented category, case-insensitivity, precedence-order tie-breaking when a query's text could match more than one category's keywords, empty/whitespace input, an unmatched query falling back to Other, invalid-form submissions leaving both fields empty, a service failure after a valid form still being categorized, and that no stored field ever contains the raw query text as a substring. Stage 1's existing suite (`planner.test_a10_stage1_analytics`) required one assertion update, since it previously assumed `query_category` stayed `None` forever; the full suite passes at 19/19 with both files together.

## Handoff to Stage 3

Stage 3 can populate the remaining nullable placeholders — token/cost estimates and `is_simulated` — without another migration. The fixed category list and keyword precedence order were confirmed by Ashley before implementation and are documented in `_QUERY_CATEGORY_KEYWORDS` in `planner/views.py`; treat a later change to that list as a deliberate, discussed decision rather than an incidental edit, since it would silently reclassify historical dashboard data.

# A9 Stage 3: Evaluation and Improvement of the Integrated AI RAG Planner

All evidence below comes from the integrated Django workflow: each case was submitted to the
authenticated page `/planitems/ai-rag-planner/` (form validation, view, service adapter, local
engine, template) by `python manage.py rag_evaluate`, using a throwaway test user that is deleted
afterwards. Models: MPNet embeddings, hybrid chunking, Top-K = 3, Qwen2.5-3B-Instruct (greedy,
300 new tokens). Run on a MacBook Air; first-request model loading is excluded from latencies.

Evidence files in this folder:

| File | Content |
|---|---|
| `stage3_results_final.csv` | Final results: 7 cases x {baseline, improved}, with answers, retrieved chunk IDs and text excerpts, similarity scores, rubric scores, latencies. This is the file the tables below are taken from |
| `stage3_runs.csv` | Raw full run (all 7 cases, both variants) made before the relevance gate existed; its X1/X2 "improved" rows are therefore superseded |
| `stage3_runs_validation_only.csv` | An earlier, identical full run kept as a repeat measurement: all 14 answers match `stage3_runs.csv` exactly; only the latencies differ by normal run-to-run variation |
| `stage3_runs_gate.csv` | Raw rerun of X1 and X2 (improved variant only) with the relevance gate installed |
| `screenshots/` | Page screenshots listed at the end |

### How `stage3_results_final.csv` was assembled

1. Start from the 14 rows of `stage3_runs.csv`.
2. Remove its two X1/X2 `improved` rows (recorded before the gate was installed; they only repeat the baseline behaviour).
3. Add the two `improved` rows from `stage3_runs_gate.csv`.
4. Sort by case (Q1-Q5, X1, X2), baseline row first.

No cell was edited, and all 14 rows keep the same columns. Q1-Q5 are not rerun for the final file because their best retrieval scores (0.527-0.762) are above the gate threshold, so the gate cannot change them; the relevance gate and output validation switches are both part of the `improved` variant, so each case was run once with them off and once with them on.

`baseline` = both Stage 3 improvements switched off (`AI_PLANNER_OUTPUT_VALIDATION=False`,
`AI_PLANNER_MIN_RELEVANCE=0`). `improved` = shipped behaviour. Generation is greedy, so both
variants get the same raw model output wherever the model runs.

Scores use the A8 rubric (`a8_rag/scoring.py`): context 0-3 from expected evidence paragraphs
(Q1-Q5 only), answer 0-3 from key points stated.

## Evaluation table (improved variant)

| Case | Test input | Expected behaviour | Retrieved chunks (score) | Context | Answer | Clean ending | Embed / retrieve / generate / total (s) |
|---|---|---|---|---|---|---|---|
| Q1 Break a large paper into tasks | "I have a big semester paper due in a few weeks. How should I break it down into tasks in CozyDay?" | Small checkable steps, milestones, conservative estimates, dependencies | HYBRID_001 (0.693), HYBRID_002 (0.672), HYBRID_003 (0.510) | 3/3 | 3/3 | yes, after trimming (raw output was cut off) | 0.015 / 0.000 / 21.02 / 21.04 |
| Q2 Prioritize assignments due the same week | "I have three assignments due this week and they all feel urgent. How do I decide what to work on first?" | Earliest firm deadline, remaining work, split the biggest job, consequences | HYBRID_003 (0.636), HYBRID_002 (0.545), HYBRID_013 (0.516) | 3/3 | 3/3 | yes | 0.019 / 0.001 / 4.99 / 5.02 |
| Q3 Weekly study plan with spaced review | "How do I build a weekly study plan and prepare for my exam using spaced review?" | Start from fixed obligations and available time, spread review over sessions, keep slack | HYBRID_006 (0.762), HYBRID_014 (0.478), HYBRID_001 (0.422) | 3/3 | 2/3 | yes | 0.020 / 0.001 / 6.65 / 6.67 |
| Q4 Share a group plan privately | "I want to share my group project plan with teammates. How do I do that without exposing private information?" | Share only deliverable/person/deadline, keep private notes out, check exports, neutral titles | HYBRID_008 (0.527), HYBRID_011 (0.445), HYBRID_012 (0.333) | 3/3 | 3/3 | yes | 0.018 / 0.001 / 15.96 / 15.99 |
| Q5 Completion analytics for a progress report | "How should I use my task completion analytics to write a weekly progress report?" | Counts are descriptive, compare with estimates/categories, report structure | HYBRID_011 (0.613), HYBRID_010 (0.547), HYBRID_004 (0.413) | 3/3 | 3/3 | yes | 0.019 / 0.001 / 18.19 / 18.22 |
| X1 Out-of-scope probe | "What is the capital of France and who designed the Eiffel Tower?" | Say the guidance does not cover it | HYBRID_003 (0.040), HYBRID_015 (0.019), HYBRID_005 (0.018) | n/a | abstains | yes | 0.296 / 0.022 / 0.00 / 0.318 |
| X2 Vague-input probe | "help" | Ask for a specific planning question | HYBRID_015 (0.183), HYBRID_009 (0.169), HYBRID_012 (0.150) | n/a | abstains | yes | 0.036 / 0.000 / 0.00 / 0.036 |

Relevance of the retrieved text can be judged in the CSV (`retrieved_text_excerpts`, first 300
characters of each chunk). Retrieval found the expected evidence paragraphs for all five main
cases, but the third chunk was weak in several of them (HYBRID_003 for Q1 at 0.510, HYBRID_012
account-access text for Q4 at 0.333, HYBRID_004 for Q5). Question-specific quality notes:

- **Q1** Steps, milestones, conservative estimates and dependencies are all present. Items 4-6
  (grouping, category labels, primary/secondary contexts) come from the unrelated categories and
  priority chunks and pad the answer. Raw output ended in a dangling "7" (Failure 1).
- **Q2** Short, complete, structured; states all three key points.
- **Q3** Spaced review, retrieval practice and checkpoints are covered, but the answer does not
  start from fixed obligations and available time even though HYBRID_006 (0.762) says so
  (Limitation A).
- **Q4** Complete numbered answer matching all three key points; the two lower-ranked chunks were
  not used.
- **Q5** Covers descriptive-not-definitive counts and comparing with estimates; it does not give
  the completed / upcoming / in progress / blocked structure even though the report chunk was
  retrieved first (rubric credits it through other wording, so the score is generous here).

Latency: embedding 0.015-0.04 s and retrieval at most 0.03 s in every run; generation is 3-21 s and
makes up over 99% of the total whenever the model runs. Answer length drives it (Q1 and Q5 use
most of the 300-token budget; Q2 and Q3 are short).

## Failures and root causes

### Failure 1: Answer cut off by the length limit (Q1)
- **What happened:** the baseline answer stops after item 6 with a dangling "7" at the 300-token
  limit and was shown as if finished.
- **Root cause category:** generation (the locked 300-token limit stops mid-text). Contributing
  factor: retrieval (a weak third chunk made the model pad with off-topic items).
- **Fix:** output validation (below). **Remaining:** the answer is shorter, not longer. A long
  question cannot get a longer answer without changing the locked generation settings.

### Failure 2: Out-of-scope question answered from general knowledge (X1)
- **What happened:** all three retrieved chunks were unrelated (similarity 0.040, 0.019, 0.018),
  yet the model answered "The capital of France is Paris. The Eiffel Tower was designed by Gustave
  Eiffel." The prompt tells it to use only the retrieved context. The page also listed three
  irrelevant "sources".
- **Root cause category:** retrieval (no minimum-relevance check; Top-K always returns three
  chunks, relevant or not), with prompt design / generation as the second factor (the model
  ignores the "only the context" instruction).

### Failure 3: Vague input produced unrelated advice (X2)
- **What happened:** the one-word query "help" passed form validation. Best similarity was 0.183.
  The model first said the context does not contain the answer, then listed account-login tips
  anyway from the unrelated HYBRID_012 chunk. 11.9 s.
- **Root cause category:** input validation (nothing rejects or redirects a vague question),
  leading to a retrieval miss and then a generation failure to abstain cleanly.

### Failure 4: Numbered list shown as one run-on paragraph (Q1, seen in the page screenshot)
- **What happened:** the model returns a numbered list with line breaks, but the page rendered the
  answer inside a single paragraph, so "1. ... 2. ... 3. ..." ran together in one block.
- **Root cause category:** UI handling (the template ignored line breaks in the answer).
- **Fix:** the answer is now rendered with Django's `linebreaks` filter, which keeps paragraph and
  line breaks and still HTML-escapes the model text. **Remaining:** the model's markdown markers
  (`**bold**`) still appear as literal asterisks because the page does not render markdown.

### Limitation A (not fixed): Q3 omits "fixed obligations"
Generation under-uses the top chunk. This matches the A8 finding that Q3 consistently misses this
point. Prompt changes would alter the locked generation module, so it is documented, not fixed.

## Improvement made

Changes to `planner/rag_engine.py` (items 1 and 2; the first is the main improvement) and to the
page template (item 3).

1. **Relevance gate (retrieved-context filtering).** If the best retrieved chunk scores below
   `AI_PLANNER_MIN_RELEVANCE` (default 0.35, set 0 to disable), the model is not called. The page
   shows "CozyDay's planning guidance does not contain enough information to answer that", the
   topics it can help with, a warning with the best relevance score, and the retrieved chunks with
   their scores. Threshold basis: best-chunk scores were 0.527-0.762 for the five in-scope cases
   and 0.040 / 0.183 for the two probes, so 0.35 sits in the gap.
2. **Output validation for cut-off answers.** If the answer does not end on terminal punctuation,
   the unfinished tail is trimmed back to the last finished sentence or list item and the page
   shows "This answer reached the length limit, so the unfinished last part was removed. Ask a
   narrower question to see the rest." Complete answers are untouched.

3. **Answer formatting.** `ai_rag_planner.html` renders the answer with `linebreaks`, so numbered
   lists and paragraphs from the model keep their line breaks (still escaped).

Also added: per-stage latencies (embedding, retrieval, generation) in the service result and on
the page, which the evaluation needs.

### Before / after on the same input

| Input | Before | After |
|---|---|---|
| X1 "What is the capital of France and who designed the Eiffel Tower?" | Model called (2.97 s generation); answered "Paris... Gustave Eiffel"; three unrelated sources shown with no warning | Model not called (generation 0.00 s, total 0.318 s); abstention message with topic suggestions; warning "best relevance 0.04" |
| X2 "help" | Model called (11.90 s); unrelated account-login tips | Model not called (total 0.036 s); same abstention message; warning "best relevance 0.18" |
| Q1 paper breakdown | Ends with dangling "7", no notice | Ends after item 6; length-limit notice shown |
| Q1 list formatting | Whole numbered list shown as one paragraph | Each paragraph and list item on its own line |
| Q2-Q5 | Reference answers | Identical answers and identical scores (no regression); best scores 0.527-0.762 are above the gate |

Quality and reliability improved: both failing inputs now give an honest, instant answer instead
of an ungrounded one, and Q1-Q5 are unchanged.

### Remaining tradeoffs
- The threshold rests on seven data points. A short but legitimate question could score below
  0.35 and be refused (false refusal); a vague question could score above it. Behaviour between
  0.18 and 0.53 is untested. The setting is adjustable.
- The gate checks the best chunk only. Weak lower-ranked chunks (Q1's 0.510, Q4's 0.333) still
  reach the model and can pad answers.
- Trimming removes content instead of completing it. In Q1 it removed only the dangling "7".
- No form-level minimum-length rule was added; "help" is stopped by the gate, not by the form.

## Regression tests (no models are loaded)

`planner/test_rag_stage3_regression.py`:
- `FinalizeAnswerTests`: complete answers unchanged; cut-off list drops only the unfinished
  item; cut-off prose; dangling list number removed; no finished sentence keeps text and warns;
  empty answer.
- `AnswerQueryValidationTests`: truncated generation trimmed with warning; switch off restores
  baseline behaviour; complete answer has no warning; stage latencies returned.
- `RelevanceGateTests`: a low-relevance query never calls the model and returns the abstention
  answer and warning; a relevant query still reaches the model; the gate can be disabled;
  threshold is configurable; default threshold sits between the measured 0.183 and 0.527.
- `PageShowsValidationTests`: the page shows the length-limit notice and per-stage latencies.
- `AnswerFormattingTests`: line breaks in the answer are preserved and answer HTML is still
  escaped.

`planner/test_rag_evaluate_command.py` checks the evaluation command against a fake engine:
baseline and improved rows for the same input, resume without duplicates, test-user cleanup, and
probe status. Full suite: 156 tests passing (`python manage.py test`).

## Reproduce

```
python manage.py rag_evaluate                      # all cases, both variants (downloads models once)
python manage.py rag_evaluate --cases X1,X2 --variants improved --out docs/ai_stage3_evaluation/stage3_runs_gate.csv
python manage.py test                              # mocked, no model download
```

## Screenshots (`docs/ai_stage3_evaluation/screenshots/`)

| File | Shows |
|---|---|
| `q1_success.png` | Q1 answer and retrieved sources, with the length-limit notice |
| `q3_success.png` | Q3 answer and retrieved sources |
| `x1_before_gate_off.png` | X1 with `AI_PLANNER_MIN_RELEVANCE=0`: ungrounded "Paris" answer |
| `x1_after_gate_on.png` | X1 with the gate: abstention message and warning |

All screenshots use the test account and the evaluation questions only; no personal data.
Neither the results nor the screenshots contain secrets, tokens or absolute paths.

## Handoff for Stage 4 (docs and demo)
- Demo path: show Q1 and Q3 as successes, then X1 before and after the gate (switch with the
  `AI_PLANNER_MIN_RELEVANCE` environment variable; restart the server between the two).
- First request after server start loads the models (several minutes); warm the app before the
  demo. Each in-scope answer takes 5-21 s on a MacBook Air.
- Failure to cite in the demo: X1 (retrieval, no relevance check). Root causes for the other two
  failures are above.
